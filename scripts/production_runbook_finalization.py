from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_runbook_finalization"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

RUNBOOK_ITEMS = [
    ("deployment_runbook", "deployment", "docs/deployment_runbook.md", True),
    ("prod_smoke_script", "deployment", "scripts/prod_smoke.ps1", True),
    ("prod_down_script", "deployment", "scripts/prod_down.ps1", True),
    ("docker_compose", "deployment", "docker-compose.yml", True),
    ("docker_compose_prod", "deployment", "docker-compose.prod.yml", True),
    ("release_gate_rollback", "rollback", "docs/release_gate_rollback_governance_pack_v39.md", True),
    ("production_deployment_drill", "rollback", "docs/production_deployment_drill_v30.md", True),
    ("incident_rehearsal", "incident", "docs/incident_rehearsal_pack_v34.md", True),
    ("failure_diagnostics", "incident", "docs/failure_diagnostics_pack_v32.md", True),
    ("operations_troubleshooting", "incident", "docs/operations_troubleshooting_index_v31.md", True),
    ("backup_restore_checklist", "dr", "docs/backup_restore_checklist_v31.md", True),
    ("backup_restore_dr_evidence", "dr", "docs/backup_restore_dr_evidence_pack_v38.md", True),
    ("operations_monitoring_backup_drill", "dr", "docs/operations_monitoring_backup_drill_v30.md", True),
    ("secret_rotation", "secret", "docs/secret_rotation_leakage_response_pack_v39.md", True),
    ("oidc_lifecycle", "secret", "docs/oidc_lifecycle_drill_v36.md", True),
    ("audit_log_plan", "audit", "docs/audit_log_plan.md", True),
    ("audit_retention_export_tests", "audit", "tests/test_audit_retention_export_v74.py", True),
    ("security_regression", "audit", "docs/security_regression_compliance_evidence_pack_v39.md", True),
    ("cross_tenant_audit", "audit", "docs/cross_tenant_audit_evidence_v36.md", True),
    ("slo_alerting", "slo", "docs/slo_alerting_runbook_pack_v38.md", True),
    ("sre_observability", "slo", "docs/sre_observability_baseline_v38.md", True),
    ("capacity_readiness", "capacity", "docs/capacity_load_test_readiness_plan_v38.md", True),
    ("launch_readiness", "launch", "docs/production_launch_readiness_review_v40.md", True),
    ("launch_blockers", "launch", "docs/launch_blocker_register_v40.md", True),
    ("launch_readiness_script", "launch", "scripts/production_launch_readiness_review.py", True),
    ("launch_blocker_script", "launch", "scripts/launch_blocker_register.py", True),
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

SECRET_FIELD_NAMES = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "jwt_secret",
    "password",
    "secret",
    "database_url",
    "redis_url",
    "webhook",
}

BOUNDARY_DECLARATIONS = [
    "只读生产 runbook 完整性索引",
    "仅检查本地文件存在性和传入 JSON 的结构化字段，不读取 Markdown 报告正文",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不修改上游报告",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
    "不连接真实外部 MCP、IdP、业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更",
    "不发送真实告警，不通知真实 on-call，不调用真实 webhook",
    "不自动批准上线",
    "不自动关闭 blocker",
    "不创建 GitHub Release",
    "不打 tag，不移动、不删除、不重建历史 tag",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称生产级 SSO/OIDC、多租户、真实 LLM、SRE/DR、容量或合规验收完成",
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


def _contains_secret_like_text(value: Any) -> bool:
    return any(pattern.search(str(value)) for pattern in SECRET_TEXT_PATTERNS)


def _contains_secret_like_payload(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key in SECRET_FIELD_NAMES and str(item).strip():
                return True
            if _contains_secret_like_payload(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret_like_payload(item) for item in value)
    return _contains_secret_like_text(value)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    return "partial" if raw else "skipped"


def _load_source(name: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
            "metadata": {},
        }

    path = Path(path_value)
    sanitized_path = _sanitize_text(path)
    if not path.exists():
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
            "metadata": {},
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "secret_detected": False,
            "metadata": {},
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
            "metadata": {},
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
            "metadata": {},
        }

    status = _normalize_status(payload.get("status") or payload.get("readiness_status"))
    secret_detected = _contains_secret_like_payload(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]

    if status == "skipped":
        missing_conditions.append(f"{name}:source_status_skipped")
    if status in {"blocked", "failed"}:
        missing_conditions.append(f"{name}:source_status_{status}")
    if payload.get("read_only") is False:
        missing_conditions.append(f"{name}:not_read_only")
    for flag in [
        "real_llm_executed",
        "external_mcp_connected",
        "external_system_connected",
        "deployment_executed",
        "migration_executed",
        "release_created",
        "tag_created",
        "rollback_executed",
        "security_scan_executed",
        "secret_rotation_executed",
        "auto_approved",
        "auto_closed",
    ]:
        if bool(payload.get(flag, False)):
            missing_conditions.append(f"{name}:{flag}_unexpected")
    if secret_detected:
        missing_conditions.append(f"{name}:secret_like_value_detected")
        warnings.append(f"{name}:secret_like_value_detected")

    metadata = {
        "go_no_go": payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {},
        "open_blocker_count": int(payload.get("open_blocker_count") or 0),
        "blocked_blocker_count": int(payload.get("blocked_blocker_count") or 0),
        "skipped_blocker_count": int(payload.get("skipped_blocker_count") or 0),
        "blocker_count": int(payload.get("blocker_count") or 0),
    }

    return {
        "name": name,
        "path": sanitized_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "secret_detected": secret_detected,
        "metadata": metadata,
    }


def _runbook_rows() -> list[dict[str, Any]]:
    rows = []
    for name, category, rel_path, required in RUNBOOK_ITEMS:
        path = ROOT_DIR / rel_path
        rows.append(
            {
                "name": name,
                "category": category,
                "path": rel_path,
                "required": required,
                "exists": path.exists(),
                "is_file": path.is_file(),
                "status": "present" if path.exists() and path.is_file() else "missing",
            }
        )
    return rows


def _derive_status(sources: list[dict[str, Any]], runbooks: list[dict[str, Any]]) -> str:
    if any(item.get("secret_detected") for item in sources):
        return "blocked"
    if any(item.get("status") in {"blocked", "failed"} for item in sources):
        return "blocked"
    if any(
        any(marker in condition for marker in ["_unexpected", "not_read_only", "secret_like_value_detected"])
        for item in sources
        for condition in item.get("missing_conditions", [])
    ):
        return "blocked"
    missing_required = [item for item in runbooks if item.get("required") and not item.get("exists")]
    if not all(item.get("provided") for item in sources):
        return "skipped"
    if any(item.get("provided") and not item.get("loaded") for item in sources):
        return "skipped"
    if not runbooks or len(missing_required) == len([item for item in runbooks if item.get("required")]):
        return "skipped"
    if missing_required:
        return "partial"
    if any(item.get("loaded") and item.get("status") == "skipped" for item in sources):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.0 Production Runbook Finalization（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- runbook_count: {payload.get('runbook_count', 0)}",
        f"- missing_required_count: {payload.get('missing_required_count', 0)}",
        "",
        "## Runbook Items",
    ]
    for item in payload.get("runbook_items", []):
        lines.append(f"- {item.get('name')}: {item.get('status')} | {item.get('category')} | {item.get('path')}")

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


def build_production_runbook_finalization(
    *,
    output_dir: str | Path | None = None,
    launch_readiness: str | Path | None = None,
    launch_blockers: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    sources = [
        _load_source("launch_readiness", launch_readiness),
        _load_source("launch_blockers", launch_blockers),
    ]
    runbooks = _runbook_rows()
    missing_required = [
        f"runbook_missing:{item['name']}"
        for item in runbooks
        if item.get("required") and not item.get("exists")
    ]
    source_missing = [condition for source in sources for condition in source.get("missing_conditions", [])]
    warnings = sorted(set(warning for source in sources for warning in source.get("warnings", [])))
    missing_conditions = sorted(set(missing_required + source_missing))
    status = _derive_status(sources, runbooks)
    launch_blocker_source = next((item for item in sources if item.get("name") == "launch_blockers"), {})
    blocker_summary = {
        "blocker_count": int(launch_blocker_source.get("metadata", {}).get("blocker_count", 0)),
        "open_blocker_count": int(launch_blocker_source.get("metadata", {}).get("open_blocker_count", 0)),
        "blocked_blocker_count": int(launch_blocker_source.get("metadata", {}).get("blocked_blocker_count", 0)),
        "skipped_blocker_count": int(launch_blocker_source.get("metadata", {}).get("skipped_blocker_count", 0)),
        "go_no_go": launch_blocker_source.get("metadata", {}).get("go_no_go", {}),
    }

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.0.0-planning",
        "phase": "v4.0_phase_20.3",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "online_endpoints_called": False,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "deployment_executed": False,
        "migration_executed": False,
        "release_created": False,
        "tag_created": False,
        "rollback_executed": False,
        "security_scan_executed": False,
        "secret_rotation_executed": False,
        "alert_sent": False,
        "oncall_notified": False,
        "auto_approved": False,
        "auto_closed": False,
        "input_sources": [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "provided": item.get("provided"),
                "exists": item.get("exists"),
                "loaded": item.get("loaded"),
                "status": item.get("status"),
                "secret_detected": item.get("secret_detected"),
                "metadata": item.get("metadata", {}),
            }
            for item in sources
        ],
        "blocker_summary": blocker_summary,
        "runbook_items": runbooks,
        "runbook_count": len(runbooks),
        "required_runbook_count": sum(1 for item in runbooks if item.get("required")),
        "missing_required_count": len(missing_required),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "生产 runbook 索引不自动批准上线；最终 Go 需要人工确认所有手册入口和演练证据。",
        },
        "next_actions": [
            "补齐缺失 required runbook 入口。",
            "串联 Launch Readiness Review 和 Launch Blocker Register 的最新 JSON 输出。",
            "为部署、回滚、incident、DR、密钥轮换、审计导出和值班升级路径补齐人工签核证据。",
            "最终生产 Go 需要人工签核，脚本不自动批准。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_runbook_finalization"
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
        "runbook_count": len(runbooks),
        "missing_required_count": len(missing_required),
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.0 生产 runbook 只读完整性索引（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--launch-readiness", default=None)
    parser.add_argument("--launch-blockers", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_production_runbook_finalization(
        output_dir=args.output_dir,
        launch_readiness=args.launch_readiness,
        launch_blockers=args.launch_blockers,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
