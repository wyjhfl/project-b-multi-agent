from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_production_acceptance"

ACCEPTANCE_DOMAINS = [
    "real_llm",
    "oidc_sso",
    "external_mcp",
    "postgres",
    "redis",
    "business_system",
    "apm_logging_alerting",
    "backup_restore_dr",
    "capacity_load_soak",
    "security_compliance",
    "release_rollback_gate",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

BOUNDARY_DECLARATIONS = [
    "只读受控生产验收演练",
    "仅消费脱敏 acceptance evidence JSON 的结构化字段",
    "不读取 Markdown 报告正文",
    "不读取或输出真实 secret 原文",
    "不连接真实 LLM、IdP、MCP、PostgreSQL、Redis、业务系统、APM、日志、告警、KMS、Vault、对象存储或云平台",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、审计导出、密钥轮换或权限变更",
    "不自动批准上线，不自动关闭 blocker，不创建 GitHub Release，不打 tag",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线，不宣称真实生产验收完成",
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


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "ready":
        return "partial"
    if raw in {"success", "partial", "skipped", "blocked", "failed"}:
        return raw
    return "skipped" if not raw else "partial"


def _load_acceptance_evidence(path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_evidence:input_not_provided"],
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
            "missing_conditions": ["acceptance_evidence:path_not_found"],
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
            "missing_conditions": ["acceptance_evidence:json_file_required"],
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
            "missing_conditions": ["acceptance_evidence:json_parse_failed"],
            "warnings": [f"acceptance_evidence:json_parse_failed:{type(exc).__name__}"],
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
            "missing_conditions": ["acceptance_evidence:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    status = _normalize_status(payload.get("status") or payload.get("readiness_status"))
    secret_detected = _contains_secret_like_payload(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]
    if status == "skipped":
        missing_conditions.append("acceptance_evidence:source_status_skipped")
    if status in {"blocked", "failed"}:
        missing_conditions.append(f"acceptance_evidence:source_status_{status}")
    if payload.get("read_only") is False:
        missing_conditions.append("acceptance_evidence:not_read_only")
    for flag in [
        "real_llm_executed",
        "external_mcp_connected",
        "external_system_connected",
        "database_connected",
        "redis_connected",
        "business_system_connected",
        "deployment_executed",
        "migration_executed",
        "release_created",
        "tag_created",
        "rollback_executed",
        "security_scan_executed",
        "secret_rotation_executed",
        "audit_export_executed",
        "auto_approved",
        "auto_closed",
    ]:
        if bool(payload.get(flag, False)):
            missing_conditions.append(f"acceptance_evidence:{flag}_unexpected")
    if secret_detected:
        missing_conditions.append("acceptance_evidence:secret_like_value_detected")
        warnings.append("acceptance_evidence:secret_like_value_detected")

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


def _acceptance_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in _safe_list(payload.get("acceptance_items") or payload.get("items")):
        if not isinstance(item, dict):
            continue
        domain = _sanitize_text(item.get("domain") or item.get("integration_id") or "")
        if domain:
            index[domain] = item
    return index


def _domain_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    payload = source.get("payload", {}) if isinstance(source.get("payload"), dict) else {}
    evidence_by_domain = _acceptance_index(payload)
    rows = []
    for domain in ACCEPTANCE_DOMAINS:
        evidence = evidence_by_domain.get(domain)
        missing: list[str] = []
        if not evidence:
            status = "skipped"
            missing.append(f"{domain}:acceptance_evidence_missing")
        else:
            status = _normalize_status(evidence.get("status") or evidence.get("readiness_status"))
            refs = [_sanitize_text(item) for item in _safe_list(evidence.get("evidence_refs"))]
            reviewer = _sanitize_text(evidence.get("reviewer") or "")
            approval_state = _sanitize_text(evidence.get("approval_state") or "not_approved")
            if not refs:
                missing.append(f"{domain}:evidence_refs_missing")
            if not reviewer:
                missing.append(f"{domain}:reviewer_missing")
            if approval_state not in {"approved", "pending_review"}:
                missing.append(f"{domain}:approval_state_not_ready")
            if status == "success":
                status = "partial"
            if evidence.get("read_only") is False:
                status = "blocked"
                missing.append(f"{domain}:not_read_only")
        rows.append(
            {
                "domain": domain,
                "status": status,
                "manual_review_required": True,
                "auto_approved": False,
                "auto_closed": False,
                "missing_conditions": missing,
            }
        )
    return rows


def _derive_status(source: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if source.get("secret_detected"):
        return "blocked"
    if source.get("status") in {"blocked", "failed"}:
        return "blocked"
    if any(
        marker in condition
        for condition in source.get("missing_conditions", [])
        for marker in ["_unexpected", "not_read_only", "secret_like_value_detected"]
    ):
        return "blocked"
    if not source.get("loaded") or source.get("status") == "skipped":
        return "skipped"
    if any(row.get("status") in {"blocked", "failed"} for row in rows):
        return "blocked"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.2 Controlled Production Acceptance Drill（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- domain_count: {payload.get('domain_count', 0)}",
        "",
        "## Domains",
    ]
    for item in payload.get("acceptance_domains", []):
        lines.append(f"- {item.get('domain')}: {item.get('status')}")
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


def build_controlled_production_acceptance_drill(
    *,
    output_dir: str | Path | None = None,
    acceptance_evidence: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    source = _load_acceptance_evidence(acceptance_evidence)
    rows = _domain_rows(source) if source.get("loaded") else []
    status = _derive_status(source, rows)
    domain_missing = [condition for row in rows for condition in row.get("missing_conditions", [])]
    missing_conditions = sorted(set(source.get("missing_conditions", []) + domain_missing))
    warnings = sorted(set(source.get("warnings", [])))

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.2.0-planning",
        "phase": "v4.2_phase_22.1",
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
        "migration_executed": False,
        "release_created": False,
        "tag_created": False,
        "rollback_executed": False,
        "security_scan_executed": False,
        "secret_rotation_executed": False,
        "audit_export_executed": False,
        "auto_approved": False,
        "auto_closed": False,
        "acceptance_evidence_source": {
            "path": source.get("path", ""),
            "provided": source.get("provided", False),
            "exists": source.get("exists", False),
            "loaded": source.get("loaded", False),
            "status": source.get("status", "skipped"),
            "secret_detected": source.get("secret_detected", False),
        },
        "acceptance_domains": rows,
        "domain_count": len(rows),
        "review_ready_domain_count": sum(1 for row in rows if row.get("status") == "partial" and not row.get("missing_conditions")),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "受控生产验收演练只消费脱敏证据，不执行真实验收动作，不自动批准上线。",
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_production_acceptance_drill"
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
        "domain_count": len(rows),
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.2 受控生产验收演练只读报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--acceptance-evidence", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_controlled_production_acceptance_drill(
        output_dir=args.output_dir,
        acceptance_evidence=args.acceptance_evidence,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
