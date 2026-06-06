from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_launch_readiness"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SOURCE_SPECS = [
    ("evidence_archive", "evidence"),
    ("pilot_closeout", "pilot"),
    ("integration_readiness", "integration"),
    ("operator_scoring", "operations"),
    ("controlled_integration", "integration"),
    ("governance_exceptions", "governance"),
    ("compliance_baseline", "security"),
    ("secret_rotation", "security"),
    ("release_gate", "release"),
    ("security_regression", "security"),
    ("sre_observability", "sre"),
    ("backup_dr", "sre"),
    ("capacity_plan", "sre"),
]

LOCAL_ARTIFACTS = [
    ("v3_5_plan", "docs/v3_5_controlled_pilot_expansion_plan.md", "pilot"),
    ("enterprise_roadmap", "docs/enterprise_production_landing_roadmap.md", "roadmap"),
    ("pilot_closeout_runbook", "docs/pilot_closeout_report_pack_v35.md", "pilot"),
    ("identity_tenant_plan", "docs/v3_6_enterprise_identity_tenant_boundary_plan.md", "identity"),
    ("real_provider_plan", "docs/v3_7_external_integration_real_provider_acceptance_plan.md", "integration"),
    ("sre_baseline_runbook", "docs/sre_observability_baseline_v38.md", "sre"),
    ("backup_dr_runbook", "docs/backup_restore_dr_evidence_pack_v38.md", "sre"),
    ("capacity_runbook", "docs/capacity_load_test_readiness_plan_v38.md", "sre"),
    ("compliance_baseline_runbook", "docs/compliance_security_baseline_v39.md", "security"),
    ("release_gate_runbook", "docs/release_gate_rollback_governance_pack_v39.md", "release"),
    ("security_regression_runbook", "docs/security_regression_compliance_evidence_pack_v39.md", "security"),
    ("release_review_v39", "docs/release_review_v3.9_compliance_security_hardening.md", "release"),
    ("launch_readiness_runbook", "docs/production_launch_readiness_review_v40.md", "launch"),
]

PRODUCTION_BLOCKERS = [
    "production_sso_oidc_signoff_missing",
    "tenant_isolation_production_acceptance_missing",
    "real_llm_production_acceptance_missing",
    "external_mcp_production_acceptance_missing",
    "business_system_integration_acceptance_missing",
    "postgres_redis_production_acceptance_missing",
    "sre_apm_alerting_oncall_acceptance_missing",
    "backup_restore_dr_failover_evidence_missing",
    "capacity_load_soak_test_evidence_missing",
    "external_security_scan_and_signoff_missing",
    "secret_rotation_leakage_response_drill_missing",
    "release_gate_change_approval_missing",
    "rollback_drill_and_freeze_window_missing",
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
    "只读生产上线评审包",
    "仅消费传入 JSON 的结构化字段和本地文件存在性，不读取 Markdown 报告正文",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
    "不连接真实外部 MCP、IdP、业务系统、数据库、Redis、APM、日志、告警、KMS、Vault、对象存储或云平台",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、DR failover、安全扫描、红队测试、审计导出、密钥轮换或权限变更",
    "不自动改变最终 Go/No-Go 结论",
    "不创建 GitHub Release",
    "不打 tag，不移动、不删除、不重建历史 tag",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称真实 LLM 生产验收完成",
    "不宣称生产级 SSO/OIDC、多租户、复杂 BI、企业级 SRE/DR/容量/合规验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _to_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return str(path)


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


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


def _normalize_status(payload: dict[str, Any]) -> str:
    raw = str(payload.get("status") or payload.get("readiness_status") or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    return "partial" if raw else "skipped"


def _load_source(name: str, scope: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "scope": scope,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    sanitized_path = _sanitize_text(path)
    if not path.exists():
        return {
            "name": name,
            "scope": scope,
            "path": sanitized_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "scope": scope,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": name,
            "scope": scope,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "scope": scope,
            "path": sanitized_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    secret_detected = _contains_secret_like_payload(payload)
    status = _normalize_status(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    skipped_reasons = [_sanitize_text(item) for item in _safe_list(payload.get("skipped_reasons"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]

    if status == "skipped":
        missing_conditions.append(f"{name}:source_status_skipped")
    if payload.get("read_only") is False:
        missing_conditions.append(f"{name}:not_read_only")
    if bool(payload.get("real_llm_executed", False)):
        missing_conditions.append(f"{name}:real_llm_executed_unexpected")
    if bool(payload.get("external_mcp_connected", False)):
        missing_conditions.append(f"{name}:external_mcp_connected_unexpected")
    if bool(payload.get("external_system_connected", False)):
        missing_conditions.append(f"{name}:external_system_connected_unexpected")
    if bool(payload.get("release_created", False)):
        missing_conditions.append(f"{name}:release_created_unexpected")
    if bool(payload.get("tag_created", False)):
        missing_conditions.append(f"{name}:tag_created_unexpected")
    if secret_detected:
        missing_conditions.append(f"{name}:secret_like_value_detected")
        warnings.append(f"{name}:secret_like_value_detected")

    return {
        "name": name,
        "scope": scope,
        "path": sanitized_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "metadata": {
            "version": _sanitize_text(payload.get("version", "")),
            "mode": _sanitize_text(payload.get("mode", "")),
            "generated_at": _sanitize_text(payload.get("generated_at", "")),
            "read_only": payload.get("read_only"),
            "missing_condition_count": len(missing_conditions) + len(skipped_reasons),
            "warning_count": len(warnings),
        },
        "missing_conditions": missing_conditions + skipped_reasons,
        "warnings": warnings,
        "secret_detected": secret_detected,
    }


def _local_artifact_rows() -> list[dict[str, Any]]:
    rows = []
    for name, rel_path, scope in LOCAL_ARTIFACTS:
        path = ROOT_DIR / rel_path
        rows.append(
            {
                "name": name,
                "scope": scope,
                "path": rel_path,
                "exists": path.exists(),
                "is_file": path.is_file(),
            }
        )
    return rows


def _derive_status(sources: list[dict[str, Any]], local_artifacts: list[dict[str, Any]]) -> str:
    if any(item.get("status") in {"blocked", "failed"} for item in sources):
        return "blocked"
    if any(item.get("secret_detected") for item in sources):
        return "blocked"
    if any(
        any(
            marker in condition
            for marker in [
                "not_read_only",
                "real_llm_executed_unexpected",
                "external_mcp_connected_unexpected",
                "external_system_connected_unexpected",
                "release_created_unexpected",
                "tag_created_unexpected",
            ]
        )
        for item in sources
        for condition in item.get("missing_conditions", [])
    ):
        return "blocked"
    provided_sources = [item for item in sources if item.get("provided")]
    loaded_sources = [item for item in provided_sources if item.get("loaded")]
    if provided_sources and not loaded_sources:
        return "skipped"
    if loaded_sources and all(item.get("status") == "skipped" for item in loaded_sources):
        return "skipped"
    if not any(item.get("exists") for item in local_artifacts):
        return "skipped"
    return "partial"


def _go_no_go(status: str, missing_conditions: list[str]) -> dict[str, Any]:
    if status == "blocked":
        recommendation = "No-Go"
        controlled_internal_pilot = "No-Go"
    elif status == "skipped":
        recommendation = "Manual-Review"
        controlled_internal_pilot = "Needs-Input"
    else:
        recommendation = "Manual-Review"
        controlled_internal_pilot = "Review-Allowed"
    return {
        "recommendation": recommendation,
        "production_direct_launch": "No-Go",
        "controlled_internal_pilot": controlled_internal_pilot,
        "auto_changed": False,
        "reason": "生产上线最终 Go 需要人工签核；只读证据汇总不能替代真实生产验收。",
        "blocking_condition_count": len(missing_conditions),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.0 Production Launch Readiness Review（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- go_no_go: {payload.get('go_no_go', {}).get('recommendation', '')}",
        f"- loaded_source_count: {payload.get('loaded_source_count', 0)}",
        "",
        "## Production Blockers",
    ]
    for item in payload.get("production_blockers", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(["", "## Local Artifacts"])
    for item in payload.get("local_artifacts", []):
        lines.append(f"- {item.get('name')}: exists={item.get('exists')} path={item.get('path')}")

    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_production_launch_readiness_review(
    *,
    output_dir: str | Path | None = None,
    evidence_archive: str | Path | None = None,
    pilot_closeout: str | Path | None = None,
    integration_readiness: str | Path | None = None,
    operator_scoring: str | Path | None = None,
    controlled_integration: str | Path | None = None,
    governance_exceptions: str | Path | None = None,
    compliance_baseline: str | Path | None = None,
    secret_rotation: str | Path | None = None,
    release_gate: str | Path | None = None,
    security_regression: str | Path | None = None,
    sre_observability: str | Path | None = None,
    backup_dr: str | Path | None = None,
    capacity_plan: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    source_paths = {
        "evidence_archive": evidence_archive,
        "pilot_closeout": pilot_closeout,
        "integration_readiness": integration_readiness,
        "operator_scoring": operator_scoring,
        "controlled_integration": controlled_integration,
        "governance_exceptions": governance_exceptions,
        "compliance_baseline": compliance_baseline,
        "secret_rotation": secret_rotation,
        "release_gate": release_gate,
        "security_regression": security_regression,
        "sre_observability": sre_observability,
        "backup_dr": backup_dr,
        "capacity_plan": capacity_plan,
    }
    input_sources = [_load_source(name, scope, source_paths.get(name)) for name, scope in SOURCE_SPECS]
    local_artifacts = _local_artifact_rows()
    missing_local_artifacts = [item["name"] for item in local_artifacts if not item.get("exists")]

    source_missing = [
        condition
        for item in input_sources
        for condition in item.get("missing_conditions", [])
        if not condition.endswith(":input_not_provided")
    ]
    missing_conditions = sorted(set(PRODUCTION_BLOCKERS + missing_local_artifacts + source_missing))
    status = _derive_status(input_sources, local_artifacts)
    loaded_source_count = sum(1 for item in input_sources if item.get("loaded"))

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.0.0-planning",
        "phase": "v4.0_phase_20.1",
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
        "input_sources": input_sources,
        "loaded_source_count": loaded_source_count,
        "local_artifacts": local_artifacts,
        "missing_local_artifacts": missing_local_artifacts,
        "production_blockers": PRODUCTION_BLOCKERS,
        "missing_conditions": missing_conditions,
        "go_no_go": _go_no_go(status, missing_conditions),
        "next_actions": [
            "为每个 production blocker 指定责任人、到期时间、补偿控制和关闭证据。",
            "补齐真实 SSO/OIDC、租户隔离、真实 LLM、外部 MCP、业务系统集成、SRE/DR、容量、安全合规、发布门禁和回滚演练证据。",
            "保持 skipped/blocked/partial 原始语义，不得在 launch readiness 中覆盖为 success。",
            "最终生产 Go 需要人工评审与管理签核，脚本不自动批准上线。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_launch_readiness"
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
        "loaded_source_count": loaded_source_count,
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.0 生产上线前只读评审包（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    for name, _scope in SOURCE_SPECS:
        parser.add_argument(f"--{name.replace('_', '-')}", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    kwargs = {name: getattr(args, name) for name, _scope in SOURCE_SPECS}
    summary = build_production_launch_readiness_review(output_dir=args.output_dir, **kwargs)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
