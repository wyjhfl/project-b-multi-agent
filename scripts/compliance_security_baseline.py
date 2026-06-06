from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "compliance_security_baseline"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"https?://[^/\s]+:[^@\s]+@"),
]

COMPLIANCE_OPT_IN_KEYS = [
    "COMPLIANCE_SECURITY_REVIEW_ENABLED",
    "COMPLIANCE_AUDIT_REVIEW_ENABLED",
    "COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED",
    "COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED",
]

COMPLIANCE_CONFIG_KEYS = [
    "APP_ENV",
    "AUTH_ENABLED",
    "RBAC_ENABLED",
    "OIDC_ENABLED",
    "AUDIT_RETENTION_ENABLED",
    "AUDIT_EXPORT_REDACTION_ENABLED",
    "STRUCTURED_LOGGING_ENABLED",
    "LOG_REDACTION_ENABLED",
    "SECURITY_HEADERS_ENABLED",
    "REQUEST_SIZE_LIMIT_ENABLED",
    "RATE_LIMIT_ENABLED",
    "ABUSE_GUARD_ENABLED",
    "JWT_SECRET",
    "DATABASE_URL",
    "REDIS_URL",
    "OIDC_CLIENT_SECRET",
]

BOUNDARY_DECLARATIONS = [
    "只读 compliance security baseline inventory",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务，不访问在线端点",
    "不连接真实 IdP、APM、日志平台、告警平台、对象存储、PostgreSQL、Redis、外部 MCP 或业务系统",
    "不执行真实安全扫描、真实审计导出、真实密钥轮换、真实权限变更、真实发布或真实回滚",
    "不修改用户、角色、权限、租户、业务数据、审计数据或指标数据",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码、告警 webhook 或生产 URL 原文",
    "不把配置模板、只读脚本或 runbook 宣称为企业级合规、安全治理或发布门禁验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_presence(keys: list[str]) -> dict[str, dict[str, Any]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _local_checks() -> dict[str, dict[str, Any]]:
    paths = {
        "deployment_guard": "app/core/deployment_guard.py",
        "security_headers": "app/core/security_headers.py",
        "request_guards": "app/core/request_guards.py",
        "structured_logging": "app/core/structured_logging.py",
        "audit_api": "app/api/audit.py",
        "audit_store": "app/storage/audit_store.py",
        "postgres_audit_store": "app/storage/postgres/audit_store.py",
        "audit_retention": "app/harness/audit/retention.py",
        "auth_dependencies": "app/auth/dependencies.py",
        "jwt_auth": "app/auth/jwt.py",
        "oidc_config": "app/auth/oidc_config.py",
        "rbac_matrix_script": "scripts/rbac_permission_matrix.py",
        "cross_tenant_audit_script": "scripts/cross_tenant_audit_evidence.py",
        "security_injection_guard": "app/harness/security/injection_guard.py",
        "risk_intent_guard": "app/harness/security/risk_intent_guard.py",
        "guardrails": "app/harness/security/guardrails.py",
        "pii_guard": "app/harness/security/pii_guard.py",
        "deployment_runbook": "docs/deployment_runbook.md",
        "security_go_no_go_review": "docs/security_go_no_go_review_v30.md",
        "production_security_baseline_plan": "docs/production_security_baseline_plan_v27.md",
        "audit_log_plan": "docs/audit_log_plan.md",
        "rbac_permission_matrix_doc": "docs/rbac_permission_matrix_v36.md",
        "cross_tenant_audit_doc": "docs/cross_tenant_audit_evidence_v36.md",
        "release_review_v38": "docs/release_review_v3.8_sre_observability_dr.md",
        "deployment_guard_tests": "tests/test_deployment_guard_v60.py",
        "security_tests": "tests/test_security_v04.py",
        "security_headers_tests": "tests/test_security_headers_v71.py",
        "request_guards_tests": "tests/test_request_guards_v72.py",
        "audit_tests": "tests/test_audit_v045.py",
        "audit_retention_tests": "tests/test_audit_retention_export_v74.py",
        "auth_tests": "tests/test_auth_v20.py",
        "rbac_tests": "tests/test_rbac_v20.py",
        "oidc_tests": "tests/test_oidc_config_v75.py",
        "guardrails_tests": "tests/test_guardrails_v44.py",
        "pii_guard_tests": "tests/test_guardrails_pii_leak_v44.py",
        "cross_tenant_audit_tests": "tests/test_cross_tenant_audit_evidence_v365.py",
    }
    return {key: {"path": path, "present": _path_exists(path)} for key, path in paths.items()}


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _missing_local(local: dict[str, dict[str, Any]], keys: list[str]) -> list[str]:
    return [f"local:{key}" for key in keys if not local.get(key, {}).get("present")]


def _check(
    check_id: str,
    *,
    status: str,
    missing_conditions: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    risk_notes: list[str] | None = None,
    recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "missing_conditions": sorted(set(missing_conditions or [])),
        "evidence": evidence or {},
        "risk_notes": risk_notes or [],
        "recommended_actions": recommended_actions or [],
    }


def _acceptance_checks(local: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    deployment_required = ["deployment_guard", "deployment_runbook", "deployment_guard_tests"]
    perimeter_required = ["security_headers", "request_guards", "security_headers_tests", "request_guards_tests"]
    logging_required = ["structured_logging", "audit_api", "audit_store", "postgres_audit_store", "audit_retention"]
    identity_required = ["auth_dependencies", "jwt_auth", "oidc_config", "auth_tests", "rbac_tests", "oidc_tests"]
    permission_required = ["rbac_matrix_script", "rbac_permission_matrix_doc", "cross_tenant_audit_script", "cross_tenant_audit_doc"]
    guardrail_required = ["security_injection_guard", "risk_intent_guard", "guardrails", "pii_guard", "guardrails_tests", "pii_guard_tests"]
    compliance_doc_required = ["security_go_no_go_review", "production_security_baseline_plan", "audit_log_plan", "release_review_v38"]
    audit_tests_required = ["audit_tests", "audit_retention_tests", "cross_tenant_audit_tests"]
    security_tests_required = ["security_tests", "security_headers_tests", "request_guards_tests", "deployment_guard_tests"]

    opt_in_missing = []
    if not _env_enabled("COMPLIANCE_SECURITY_REVIEW_ENABLED"):
        opt_in_missing.append("opt_in:COMPLIANCE_SECURITY_REVIEW_ENABLED_not_enabled")
    if not _env_enabled("COMPLIANCE_AUDIT_REVIEW_ENABLED"):
        opt_in_missing.append("opt_in:COMPLIANCE_AUDIT_REVIEW_ENABLED_not_enabled")
    if not _env_enabled("COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED"):
        opt_in_missing.append("opt_in:COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED_not_enabled")
    opt_in_missing.append("evidence:formal_compliance_signoff_missing")

    secret_rotation_missing = []
    if not _env_enabled("COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED"):
        secret_rotation_missing.append("opt_in:COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED_not_enabled")
    secret_rotation_missing.append("evidence:secret_rotation_drill_report_missing")

    return [
        _check(
            "deployment_gate_and_release_boundary",
            status="partial" if not _missing_local(local, deployment_required) else "skipped",
            missing_conditions=_missing_local(local, deployment_required),
            evidence={key: local[key] for key in deployment_required if key in local},
            risk_notes=["deployment guard 存在不等于真实发布签核、变更审批或回滚演练完成。"],
        ),
        _check(
            "security_headers_request_guards",
            status="partial" if not _missing_local(local, perimeter_required) else "skipped",
            missing_conditions=_missing_local(local, perimeter_required),
            evidence={key: local[key] for key in perimeter_required if key in local},
            risk_notes=["当前 request guard 为应用内控制，不等于网关级或多实例生产防护完成。"],
        ),
        _check(
            "audit_logging_retention_redaction",
            status="partial" if not _missing_local(local, logging_required) else "skipped",
            missing_conditions=_missing_local(local, logging_required),
            evidence={key: local[key] for key in logging_required if key in local},
            recommended_actions=["后续需补充审计导出授权、留存周期签核、脱敏字段复核和证据链完整性评审。"],
        ),
        _check(
            "identity_rbac_oidc_boundary",
            status="partial" if not _missing_local(local, identity_required) else "skipped",
            missing_conditions=_missing_local(local, identity_required),
            evidence={key: local[key] for key in identity_required if key in local},
            risk_notes=["默认 AUTH/RBAC/OIDC 仍不启用；生产级 SSO/OIDC 仍需真实 IdP 验收。"],
        ),
        _check(
            "permission_and_cross_tenant_evidence",
            status="partial" if not _missing_local(local, permission_required) else "skipped",
            missing_conditions=_missing_local(local, permission_required),
            evidence={key: local[key] for key in permission_required if key in local},
            recommended_actions=["后续需把权限申请、定期复核、离职回收和跨租户拒绝证据纳入制度化流程。"],
        ),
        _check(
            "prompt_pii_guardrail_security",
            status="partial" if not _missing_local(local, guardrail_required) else "skipped",
            missing_conditions=_missing_local(local, guardrail_required),
            evidence={key: local[key] for key in guardrail_required if key in local},
            risk_notes=["本地 guardrail 测试不等于真实红队或合规安全测试完成。"],
        ),
        _check(
            "compliance_documentation_baseline",
            status="partial" if not _missing_local(local, compliance_doc_required) else "skipped",
            missing_conditions=_missing_local(local, compliance_doc_required),
            evidence={key: local[key] for key in compliance_doc_required if key in local},
        ),
        _check(
            "formal_review_and_signoff",
            status="partial" if not opt_in_missing else "skipped",
            missing_conditions=opt_in_missing,
            evidence={
                "env": _env_presence(
                    [
                        "COMPLIANCE_SECURITY_REVIEW_ENABLED",
                        "COMPLIANCE_AUDIT_REVIEW_ENABLED",
                        "COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED",
                    ]
                ),
                "formal_signoff_recorded": False,
            },
            risk_notes=["缺少正式合规签核证据时必须 skipped，不得伪造成成功。"],
        ),
        _check(
            "secret_rotation_readiness",
            status="partial" if not secret_rotation_missing else "skipped",
            missing_conditions=secret_rotation_missing,
            evidence={
                "env": _env_presence(["COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED"]),
                "secret_rotation_executed": False,
            },
            risk_notes=["本阶段不执行真实密钥轮换；缺少演练报告时不得宣称密钥治理完成。"],
        ),
        _check(
            "regression_test_coverage",
            status="partial" if not _missing_local(local, audit_tests_required + security_tests_required) else "skipped",
            missing_conditions=_missing_local(local, audit_tests_required + security_tests_required),
            evidence={key: local[key] for key in audit_tests_required + security_tests_required if key in local},
        ),
    ]


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.9 compliance security baseline inventory（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- security_scan_executed: `{payload['security_scan_executed']}`",
        f"- audit_export_executed: `{payload['audit_export_executed']}`",
        f"- secret_rotation_executed: `{payload['secret_rotation_executed']}`",
        f"- release_or_rollback_executed: `{payload['release_or_rollback_executed']}`",
        f"- check_count: `{payload['check_count']}`",
        f"- missing_count: `{payload['missing_count']}`",
        "",
        "## 检查项",
    ]
    for item in payload["acceptance_checks"]:
        lines.extend(
            [
                "",
                f"### {item['check_id']}",
                f"- status: `{item['status']}`",
                f"- missing_conditions: `{json.dumps(item['missing_conditions'], ensure_ascii=False)}`",
            ]
        )
        for note in item.get("risk_notes", []):
            lines.append(f"- risk: {note}")
        for action in item.get("recommended_actions", []):
            lines.append(f"- next_action: {action}")
    lines.extend(["", "## 边界声明"])
    lines.extend(f"- {item}" for item in payload["boundary_declarations"])
    lines.append("")
    return "\n".join(lines)


def build_compliance_security_baseline(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_path = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    local = _local_checks()
    acceptance_checks = _acceptance_checks(local)
    missing_conditions = sorted(
        {
            condition
            for item in acceptance_checks
            for condition in item.get("missing_conditions", [])
        }
    )
    blocked_secret_output = any(
        _contains_secret_like_text(item)
        for item in [
            _env_presence(COMPLIANCE_OPT_IN_KEYS + COMPLIANCE_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.9.0",
        "phase": "v3.9 Phase 19.1",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "service_started": False,
        "online_endpoints_called": False,
        "external_system_connected": False,
        "security_scan_executed": False,
        "audit_export_executed": False,
        "secret_rotation_executed": False,
        "permission_change_executed": False,
        "release_or_rollback_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(COMPLIANCE_OPT_IN_KEYS + COMPLIANCE_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "补充正式合规签核、审计留存签核、权限复核和发布门禁审批证据。",
            "进入 Phase 19.2 密钥轮换与泄漏响应证据包，保持默认只读。",
            "保持默认 fake/offline，不把配置模板或 runbook 视为企业级合规验收完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_compliance_security_baseline"
    json_path = output_path / f"{stem}.json"
    markdown_path = output_path / f"{stem}.md"
    payload["output_dir"] = str(output_path)
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(markdown_path)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "read_only": payload["read_only"],
        "online_endpoints_called": payload["online_endpoints_called"],
        "external_system_connected": payload["external_system_connected"],
        "security_scan_executed": payload["security_scan_executed"],
        "audit_export_executed": payload["audit_export_executed"],
        "secret_rotation_executed": payload["secret_rotation_executed"],
        "release_or_rollback_executed": payload["release_or_rollback_executed"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.9 compliance security baseline inventory（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_compliance_security_baseline(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
