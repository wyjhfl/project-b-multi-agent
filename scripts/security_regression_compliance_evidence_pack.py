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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "security_regression_compliance_evidence"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"https?://[^/\s]+:[^@\s]+@"),
]

SECURITY_OPT_IN_KEYS = [
    "SECURITY_REGRESSION_REVIEW_ENABLED",
    "SECURITY_SCAN_REVIEW_ENABLED",
    "COMPLIANCE_EVIDENCE_REVIEW_ENABLED",
]

SECURITY_CONFIG_KEYS = [
    "AUTH_ENABLED",
    "RBAC_ENABLED",
    "OIDC_ENABLED",
    "SECURITY_HEADERS_ENABLED",
    "REQUEST_SIZE_LIMIT_ENABLED",
    "RATE_LIMIT_ENABLED",
    "ABUSE_GUARD_ENABLED",
    "AUDIT_EXPORT_REDACTION_ENABLED",
    "LOG_REDACTION_ENABLED",
    "JWT_SECRET",
    "DATABASE_URL",
    "REDIS_URL",
]

BOUNDARY_DECLARATIONS = [
    "只读 security regression and compliance evidence pack",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件、脚本和 runbook 文件存在性",
    "不启动服务，不访问在线端点",
    "不执行真实 SAST、DAST、依赖扫描、红队测试、外部审计或外部系统调用",
    "不连接真实 IdP、LLM provider、外部 MCP、业务系统、数据库、Redis、APM、日志平台或告警平台",
    "不修改用户、角色、权限、租户、业务数据、审计数据、指标数据或配置文件",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文",
    "不把本地测试存在性、runbook 或只读证据索引宣称为企业级安全合规验收完成",
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
        "injection_guard": "app/harness/security/injection_guard.py",
        "risk_intent_guard": "app/harness/security/risk_intent_guard.py",
        "guardrails": "app/harness/security/guardrails.py",
        "pii_guard": "app/harness/security/pii_guard.py",
        "sql_guard": "app/agent/nl2sql/sql_guard.py",
        "security_headers": "app/core/security_headers.py",
        "request_guards": "app/core/request_guards.py",
        "auth_dependencies": "app/auth/dependencies.py",
        "audit_api": "app/api/audit.py",
        "structured_logging": "app/core/structured_logging.py",
        "rbac_matrix_script": "scripts/rbac_permission_matrix.py",
        "cross_tenant_audit_script": "scripts/cross_tenant_audit_evidence.py",
        "compliance_baseline_script": "scripts/compliance_security_baseline.py",
        "secret_rotation_script": "scripts/secret_rotation_leakage_response_pack.py",
        "release_gate_script": "scripts/release_gate_rollback_governance_pack.py",
        "security_tests": "tests/test_security_v04.py",
        "guardrails_tests": "tests/test_guardrails_v44.py",
        "pii_guard_tests": "tests/test_guardrails_pii_leak_v44.py",
        "security_headers_tests": "tests/test_security_headers_v71.py",
        "request_guards_tests": "tests/test_request_guards_v72.py",
        "auth_tests": "tests/test_auth_v20.py",
        "rbac_tests": "tests/test_rbac_v20.py",
        "cross_tenant_audit_tests": "tests/test_cross_tenant_audit_evidence_v365.py",
        "audit_tests": "tests/test_audit_v045.py",
        "audit_retention_tests": "tests/test_audit_retention_export_v74.py",
        "deployment_guard_tests": "tests/test_deployment_guard_v60.py",
        "security_go_no_go_review": "docs/security_go_no_go_review_v30.md",
        "production_security_baseline_plan": "docs/production_security_baseline_plan_v27.md",
        "compliance_baseline_runbook": "docs/compliance_security_baseline_v39.md",
        "release_gate_runbook": "docs/release_gate_rollback_governance_pack_v39.md",
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
    prompt_required = ["injection_guard", "risk_intent_guard", "guardrails", "guardrails_tests"]
    pii_required = ["pii_guard", "pii_guard_tests", "structured_logging"]
    sql_required = ["sql_guard", "security_tests"]
    perimeter_required = ["security_headers", "request_guards", "security_headers_tests", "request_guards_tests"]
    auth_required = ["auth_dependencies", "auth_tests", "rbac_tests", "rbac_matrix_script"]
    tenant_required = ["cross_tenant_audit_script", "cross_tenant_audit_tests"]
    audit_required = ["audit_api", "audit_tests", "audit_retention_tests"]
    compliance_required = [
        "compliance_baseline_script",
        "secret_rotation_script",
        "release_gate_script",
        "security_go_no_go_review",
        "production_security_baseline_plan",
        "compliance_baseline_runbook",
        "release_gate_runbook",
    ]
    release_required = ["deployment_guard_tests", "release_gate_script", "release_gate_runbook"]

    scan_missing = []
    if not _env_enabled("SECURITY_SCAN_REVIEW_ENABLED"):
        scan_missing.append("opt_in:SECURITY_SCAN_REVIEW_ENABLED_not_enabled")
    scan_missing.append("evidence:external_security_scan_report_missing")

    signoff_missing = []
    if not _env_enabled("SECURITY_REGRESSION_REVIEW_ENABLED"):
        signoff_missing.append("opt_in:SECURITY_REGRESSION_REVIEW_ENABLED_not_enabled")
    if not _env_enabled("COMPLIANCE_EVIDENCE_REVIEW_ENABLED"):
        signoff_missing.append("opt_in:COMPLIANCE_EVIDENCE_REVIEW_ENABLED_not_enabled")
    signoff_missing.append("evidence:security_compliance_signoff_missing")

    return [
        _check(
            "prompt_injection_guard_regression",
            status="partial" if not _missing_local(local, prompt_required) else "skipped",
            missing_conditions=_missing_local(local, prompt_required),
            evidence={key: local[key] for key in prompt_required if key in local},
        ),
        _check(
            "pii_redaction_regression",
            status="partial" if not _missing_local(local, pii_required) else "skipped",
            missing_conditions=_missing_local(local, pii_required),
            evidence={key: local[key] for key in pii_required if key in local},
        ),
        _check(
            "sql_guard_security_regression",
            status="partial" if not _missing_local(local, sql_required) else "skipped",
            missing_conditions=_missing_local(local, sql_required),
            evidence={key: local[key] for key in sql_required if key in local},
        ),
        _check(
            "perimeter_guard_regression",
            status="partial" if not _missing_local(local, perimeter_required) else "skipped",
            missing_conditions=_missing_local(local, perimeter_required),
            evidence={key: local[key] for key in perimeter_required if key in local},
            risk_notes=["应用内 request guard 不等于网关级或多实例生产防护完成。"],
        ),
        _check(
            "auth_rbac_permission_regression",
            status="partial" if not _missing_local(local, auth_required) else "skipped",
            missing_conditions=_missing_local(local, auth_required),
            evidence={key: local[key] for key in auth_required if key in local},
        ),
        _check(
            "cross_tenant_denial_evidence",
            status="partial" if not _missing_local(local, tenant_required) else "skipped",
            missing_conditions=_missing_local(local, tenant_required),
            evidence={key: local[key] for key in tenant_required if key in local},
            risk_notes=["当前跨租户证据仍是模板与只读证据，不等于生产多租户 enforcement 完成。"],
        ),
        _check(
            "audit_export_redaction_regression",
            status="partial" if not _missing_local(local, audit_required) else "skipped",
            missing_conditions=_missing_local(local, audit_required),
            evidence={key: local[key] for key in audit_required if key in local},
        ),
        _check(
            "release_gate_security_linkage",
            status="partial" if not _missing_local(local, release_required) else "skipped",
            missing_conditions=_missing_local(local, release_required),
            evidence={key: local[key] for key in release_required if key in local},
        ),
        _check(
            "compliance_evidence_linkage",
            status="partial" if not _missing_local(local, compliance_required) else "skipped",
            missing_conditions=_missing_local(local, compliance_required),
            evidence={key: local[key] for key in compliance_required if key in local},
        ),
        _check(
            "external_security_scan_and_signoff",
            status="partial" if not scan_missing + signoff_missing else "skipped",
            missing_conditions=scan_missing + signoff_missing,
            evidence={
                "env": _env_presence(
                    [
                        "SECURITY_REGRESSION_REVIEW_ENABLED",
                        "SECURITY_SCAN_REVIEW_ENABLED",
                        "COMPLIANCE_EVIDENCE_REVIEW_ENABLED",
                    ]
                ),
                "external_security_scan_executed": False,
                "formal_security_signoff_recorded": False,
            },
            risk_notes=["缺少外部安全扫描与正式签核时必须 skipped，不得伪造成成功。"],
        ),
    ]


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.9 security regression and compliance evidence pack（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- external_security_scan_executed: `{payload['external_security_scan_executed']}`",
        f"- online_endpoints_called: `{payload['online_endpoints_called']}`",
        f"- formal_security_signoff_recorded: `{payload['formal_security_signoff_recorded']}`",
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


def build_security_regression_compliance_evidence_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(SECURITY_OPT_IN_KEYS + SECURITY_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.9.0",
        "phase": "v3.9 Phase 19.4",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "service_started": False,
        "online_endpoints_called": False,
        "external_system_connected": False,
        "external_security_scan_executed": False,
        "formal_security_signoff_recorded": False,
        "permission_change_executed": False,
        "audit_export_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(SECURITY_OPT_IN_KEYS + SECURITY_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "补充外部安全扫描或红队报告、正式安全签核和合规证据复核记录。",
            "将 prompt/PII/SQL/权限/跨租户/审计/发布门禁测试纳入 release gate。",
            "保持默认只读，不把测试文件存在性视为企业级安全合规验收完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_security_regression_compliance_evidence_pack"
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
        "external_security_scan_executed": payload["external_security_scan_executed"],
        "formal_security_signoff_recorded": payload["formal_security_signoff_recorded"],
        "audit_export_executed": payload["audit_export_executed"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.9 security regression and compliance evidence pack（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_security_regression_compliance_evidence_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
