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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "secret_rotation_leakage_response"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"https?://[^/\s]+:[^@\s]+@"),
]

SECRET_OPT_IN_KEYS = [
    "SECRET_ROTATION_REVIEW_ENABLED",
    "SECRET_LEAKAGE_DRILL_ENABLED",
    "SECRET_REVOCATION_DRILL_ENABLED",
]

SECRET_CONFIG_KEYS = [
    "JWT_SECRET",
    "DATABASE_URL",
    "REDIS_URL",
    "OIDC_CLIENT_SECRET",
    "REAL_LLM_API_KEY_ENV",
    "MCP_REAL_COMMAND",
    "BUSINESS_SYSTEM_API_KEY_ENV",
    "SRE_ALERT_WEBHOOK",
]

BOUNDARY_DECLARATIONS = [
    "只读 secret rotation and leakage response pack",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不读取 .env 或任何真实 secret 值",
    "不连接真实 KMS、Vault、云平台、IdP、LLM provider、外部 MCP、数据库、Redis、告警平台或业务系统",
    "不执行真实密钥创建、轮换、撤销、禁用、泄漏扫描或告警通知",
    "不修改用户、角色、权限、租户、业务数据、审计数据、指标数据或配置文件",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文",
    "不把配置模板、env name、只读脚本或 runbook 宣称为企业级密钥治理完成",
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
        "env_example": ".env.example",
        "env_production_example": ".env.production.example",
        "deployment_guard": "app/core/deployment_guard.py",
        "structured_logging": "app/core/structured_logging.py",
        "audit_api": "app/api/audit.py",
        "audit_store": "app/storage/audit_store.py",
        "audit_retention": "app/harness/audit/retention.py",
        "oidc_config": "app/auth/oidc_config.py",
        "jwt_auth": "app/auth/jwt.py",
        "config_drift_script": "scripts/config_drift_check.py",
        "governance_exception_script": "scripts/governance_exception_register.py",
        "compliance_baseline_script": "scripts/compliance_security_baseline.py",
        "optional_integration_readiness_script": "scripts/optional_integration_readiness.py",
        "controlled_integration_dry_run_script": "scripts/controlled_integration_dry_run.py",
        "deployment_runbook": "docs/deployment_runbook.md",
        "config_drift_runbook": "docs/config_drift_checklist_v33.md",
        "governance_exception_runbook": "docs/governance_exception_register_v35.md",
        "oidc_lifecycle_runbook": "docs/oidc_lifecycle_drill_v36.md",
        "compliance_baseline_runbook": "docs/compliance_security_baseline_v39.md",
        "deployment_guard_tests": "tests/test_deployment_guard_v60.py",
        "structured_logging_tests": "tests/test_structured_logging_v73.py",
        "audit_tests": "tests/test_audit_v045.py",
        "audit_retention_tests": "tests/test_audit_retention_export_v74.py",
        "oidc_tests": "tests/test_oidc_config_v75.py",
        "config_drift_tests": "tests/test_config_drift_v332.py",
        "compliance_baseline_tests": "tests/test_compliance_security_baseline_v391.py",
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
    inventory_required = ["env_example", "env_production_example", "deployment_guard", "config_drift_script"]
    redaction_required = ["structured_logging", "audit_api", "audit_store", "audit_retention"]
    identity_secret_required = ["oidc_config", "jwt_auth", "oidc_lifecycle_runbook", "oidc_tests"]
    governance_required = ["governance_exception_script", "governance_exception_runbook", "compliance_baseline_script", "compliance_baseline_runbook"]
    integration_required = ["optional_integration_readiness_script", "controlled_integration_dry_run_script"]
    test_required = ["deployment_guard_tests", "audit_tests", "audit_retention_tests", "config_drift_tests", "compliance_baseline_tests"]

    rotation_missing = []
    if not _env_enabled("SECRET_ROTATION_REVIEW_ENABLED"):
        rotation_missing.append("opt_in:SECRET_ROTATION_REVIEW_ENABLED_not_enabled")
    rotation_missing.append("evidence:secret_rotation_drill_report_missing")

    leakage_missing = []
    if not _env_enabled("SECRET_LEAKAGE_DRILL_ENABLED"):
        leakage_missing.append("opt_in:SECRET_LEAKAGE_DRILL_ENABLED_not_enabled")
    leakage_missing.append("evidence:secret_leakage_response_report_missing")

    revocation_missing = []
    if not _env_enabled("SECRET_REVOCATION_DRILL_ENABLED"):
        revocation_missing.append("opt_in:SECRET_REVOCATION_DRILL_ENABLED_not_enabled")
    revocation_missing.append("evidence:secret_revocation_drill_report_missing")

    return [
        _check(
            "secret_surface_inventory",
            status="partial" if not _missing_local(local, inventory_required) else "skipped",
            missing_conditions=_missing_local(local, inventory_required),
            evidence={
                "local": {key: local[key] for key in inventory_required if key in local},
                "env": _env_presence(SECRET_CONFIG_KEYS),
            },
            risk_notes=["仅输出 env name 与 present 布尔状态，不读取或输出真实 secret 值。"],
        ),
        _check(
            "redaction_and_audit_boundary",
            status="partial" if not _missing_local(local, redaction_required) else "skipped",
            missing_conditions=_missing_local(local, redaction_required),
            evidence={key: local[key] for key in redaction_required if key in local},
            recommended_actions=["后续需补充泄漏响应时的审计事件类型、脱敏字段复核和访问授权记录。"],
        ),
        _check(
            "identity_secret_lifecycle",
            status="partial" if not _missing_local(local, identity_secret_required) else "skipped",
            missing_conditions=_missing_local(local, identity_secret_required),
            evidence={key: local[key] for key in identity_secret_required if key in local},
            risk_notes=["OIDC/JWT 生命周期材料存在不等于真实 IdP client_secret 或 JWT_SECRET 轮换已完成。"],
        ),
        _check(
            "external_integration_secret_boundary",
            status="partial" if not _missing_local(local, integration_required) else "skipped",
            missing_conditions=_missing_local(local, integration_required),
            evidence={key: local[key] for key in integration_required if key in local},
            risk_notes=["真实 LLM/MCP/业务系统密钥仍需单独 opt-in 和人工受控验收。"],
        ),
        _check(
            "governance_exception_linkage",
            status="partial" if not _missing_local(local, governance_required) else "skipped",
            missing_conditions=_missing_local(local, governance_required),
            evidence={key: local[key] for key in governance_required if key in local},
            recommended_actions=["密钥例外、延期轮换和补偿控制应进入治理例外登记。"],
        ),
        _check(
            "rotation_drill_evidence",
            status="partial" if not rotation_missing else "skipped",
            missing_conditions=rotation_missing,
            evidence={
                "env": _env_presence(["SECRET_ROTATION_REVIEW_ENABLED"]),
                "secret_rotation_executed": False,
            },
            risk_notes=["本阶段不执行真实密钥轮换；缺少演练报告时必须 skipped。"],
        ),
        _check(
            "leakage_response_evidence",
            status="partial" if not leakage_missing else "skipped",
            missing_conditions=leakage_missing,
            evidence={
                "env": _env_presence(["SECRET_LEAKAGE_DRILL_ENABLED"]),
                "leakage_scan_executed": False,
                "alert_sent": False,
            },
            risk_notes=["本阶段不执行真实泄漏扫描或告警；缺少响应演练报告时不得伪造成成功。"],
        ),
        _check(
            "revocation_and_recovery_evidence",
            status="partial" if not revocation_missing else "skipped",
            missing_conditions=revocation_missing,
            evidence={
                "env": _env_presence(["SECRET_REVOCATION_DRILL_ENABLED"]),
                "secret_revocation_executed": False,
            },
            recommended_actions=["后续需补充撤销、回滚、服务恢复、缓存刷新和依赖通知证据。"],
        ),
        _check(
            "regression_test_coverage",
            status="partial" if not _missing_local(local, test_required) else "skipped",
            missing_conditions=_missing_local(local, test_required),
            evidence={key: local[key] for key in test_required if key in local},
        ),
    ]


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.9 secret rotation and leakage response pack（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- secret_rotation_executed: `{payload['secret_rotation_executed']}`",
        f"- leakage_scan_executed: `{payload['leakage_scan_executed']}`",
        f"- secret_revocation_executed: `{payload['secret_revocation_executed']}`",
        f"- secret_plaintext_output: `{payload['secret_plaintext_output']}`",
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


def build_secret_rotation_leakage_response_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(SECRET_OPT_IN_KEYS + SECRET_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.9.0",
        "phase": "v3.9 Phase 19.2",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "service_started": False,
        "online_endpoints_called": False,
        "external_secret_system_connected": False,
        "external_system_connected": False,
        "secret_rotation_executed": False,
        "secret_revocation_executed": False,
        "leakage_scan_executed": False,
        "alert_sent": False,
        "config_file_modified": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(SECRET_OPT_IN_KEYS + SECRET_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "补充 JWT_SECRET、OIDC_CLIENT_SECRET、DATABASE_URL、REDIS_URL、LLM API key、MCP command 和业务系统 secret 的轮换窗口与负责人。",
            "补充泄漏响应演练、撤销恢复演练、审计事件样例和治理例外流程。",
            "保持默认只读，不把 env name 或配置模板视为密钥治理完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_secret_rotation_leakage_response_pack"
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
        "external_secret_system_connected": payload["external_secret_system_connected"],
        "secret_rotation_executed": payload["secret_rotation_executed"],
        "secret_revocation_executed": payload["secret_revocation_executed"],
        "leakage_scan_executed": payload["leakage_scan_executed"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.9 secret rotation and leakage response pack（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_secret_rotation_leakage_response_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
