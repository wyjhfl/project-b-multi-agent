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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "release_gate_rollback_governance"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"https?://[^/\s]+:[^@\s]+@"),
]

RELEASE_OPT_IN_KEYS = [
    "RELEASE_GATE_REVIEW_ENABLED",
    "RELEASE_ROLLBACK_DRILL_ENABLED",
    "RELEASE_CHANGE_APPROVAL_ENABLED",
]

RELEASE_CONFIG_KEYS = [
    "APP_ENV",
    "STORAGE_BACKEND",
    "AUTH_ENABLED",
    "RBAC_ENABLED",
    "OIDC_ENABLED",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "RELEASE_FREEZE_WINDOW",
    "RELEASE_APPROVER",
]

BOUNDARY_DECLARATIONS = [
    "只读 release gate and rollback governance pack",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务，不访问在线端点",
    "不执行 git tag、GitHub Release、部署、迁移、回滚、数据恢复或外部系统调用",
    "不连接真实 PostgreSQL、Redis、IdP、LLM provider、外部 MCP、业务系统、APM、日志平台或告警平台",
    "不写业务数据、审计数据、指标数据或配置文件",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码、webhook 或生产 URL 原文",
    "不把 release notes、release review、runbook 或配置模板宣称为生产发布门禁或回滚验收完成",
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
        "deployment_api": "app/api/deployment.py",
        "docker_compose": "docker-compose.yml",
        "docker_compose_prod": "docker-compose.prod.yml",
        "dockerfile": "Dockerfile",
        "alembic_env": "alembic/env.py",
        "pyproject": "pyproject.toml",
        "release_notes_v38": "RELEASE_NOTES_v3.8.0.md",
        "release_review_v38": "docs/release_review_v3.8_sre_observability_dr.md",
        "deployment_runbook": "docs/deployment_runbook.md",
        "production_deployment_drill": "docs/production_deployment_drill_v30.md",
        "security_go_no_go_review": "docs/security_go_no_go_review_v30.md",
        "production_readiness_checklist": "docs/production_readiness_checklist.md",
        "backup_dr_runbook": "docs/backup_restore_dr_evidence_pack_v38.md",
        "compliance_baseline_runbook": "docs/compliance_security_baseline_v39.md",
        "secret_rotation_runbook": "docs/secret_rotation_leakage_response_pack_v39.md",
        "failure_diagnostics_script": "scripts/failure_diagnostics.py",
        "evidence_archive_script": "scripts/evidence_archive_manifest.py",
        "deployment_guard_tests": "tests/test_deployment_guard_v60.py",
        "storage_tests": "tests/test_storage_v20.py",
        "request_guard_tests": "tests/test_request_guards_v72.py",
        "compliance_baseline_tests": "tests/test_compliance_security_baseline_v391.py",
        "backup_dr_tests": "tests/test_backup_restore_dr_evidence_pack_v383.py",
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
    gate_required = ["deployment_guard", "deployment_api", "deployment_runbook", "production_readiness_checklist"]
    artifact_required = ["pyproject", "release_notes_v38", "release_review_v38", "security_go_no_go_review"]
    deploy_required = ["docker_compose", "docker_compose_prod", "dockerfile", "alembic_env"]
    rollback_required = ["production_deployment_drill", "backup_dr_runbook", "failure_diagnostics_script", "evidence_archive_script"]
    governance_required = ["compliance_baseline_runbook", "secret_rotation_runbook", "release_review_v38"]
    test_required = ["deployment_guard_tests", "storage_tests", "request_guard_tests", "compliance_baseline_tests", "backup_dr_tests"]

    approval_missing = []
    if not _env_enabled("RELEASE_CHANGE_APPROVAL_ENABLED"):
        approval_missing.append("opt_in:RELEASE_CHANGE_APPROVAL_ENABLED_not_enabled")
    approval_missing.append("evidence:release_change_approval_record_missing")

    gate_missing = []
    if not _env_enabled("RELEASE_GATE_REVIEW_ENABLED"):
        gate_missing.append("opt_in:RELEASE_GATE_REVIEW_ENABLED_not_enabled")
    gate_missing.append("evidence:release_gate_signoff_missing")

    rollback_missing = []
    if not _env_enabled("RELEASE_ROLLBACK_DRILL_ENABLED"):
        rollback_missing.append("opt_in:RELEASE_ROLLBACK_DRILL_ENABLED_not_enabled")
    rollback_missing.append("evidence:rollback_drill_report_missing")

    return [
        _check(
            "deployment_gate_inventory",
            status="partial" if not _missing_local(local, gate_required) else "skipped",
            missing_conditions=_missing_local(local, gate_required),
            evidence={key: local[key] for key in gate_required if key in local},
            risk_notes=["deployment guard 存在不等于真实生产发布门禁签核完成。"],
        ),
        _check(
            "release_artifact_readiness",
            status="partial" if not _missing_local(local, artifact_required) else "skipped",
            missing_conditions=_missing_local(local, artifact_required),
            evidence={key: local[key] for key in artifact_required if key in local},
        ),
        _check(
            "deployment_and_migration_precheck",
            status="partial" if not _missing_local(local, deploy_required) else "skipped",
            missing_conditions=_missing_local(local, deploy_required),
            evidence={key: local[key] for key in deploy_required if key in local},
            risk_notes=["本阶段不执行 compose、Docker build、Alembic migration 或真实部署。"],
        ),
        _check(
            "change_approval_evidence",
            status="partial" if not approval_missing else "skipped",
            missing_conditions=approval_missing,
            evidence={
                "env": _env_presence(["RELEASE_CHANGE_APPROVAL_ENABLED", "RELEASE_APPROVER", "RELEASE_FREEZE_WINDOW"]),
                "change_approval_recorded": False,
            },
            risk_notes=["缺少变更审批记录时必须 skipped，不得伪造成发布批准。"],
        ),
        _check(
            "release_gate_signoff_evidence",
            status="partial" if not gate_missing else "skipped",
            missing_conditions=gate_missing,
            evidence={
                "env": _env_presence(["RELEASE_GATE_REVIEW_ENABLED", "APP_ENV", "AUTH_ENABLED", "RBAC_ENABLED"]),
                "release_gate_signed": False,
            },
            recommended_actions=["后续需补充配置预检、迁移预检、测试门禁、安全复核、合规签核和发布负责人记录。"],
        ),
        _check(
            "rollback_drill_evidence",
            status="partial" if not rollback_missing else "skipped",
            missing_conditions=rollback_missing,
            evidence={
                "env": _env_presence(["RELEASE_ROLLBACK_DRILL_ENABLED"]),
                "rollback_executed": False,
            },
            risk_notes=["本阶段不执行真实回滚；缺少演练报告时不得宣称回滚能力完成。"],
        ),
        _check(
            "rollback_runbook_linkage",
            status="partial" if not _missing_local(local, rollback_required) else "skipped",
            missing_conditions=_missing_local(local, rollback_required),
            evidence={key: local[key] for key in rollback_required if key in local},
        ),
        _check(
            "governance_security_linkage",
            status="partial" if not _missing_local(local, governance_required) else "skipped",
            missing_conditions=_missing_local(local, governance_required),
            evidence={key: local[key] for key in governance_required if key in local},
            recommended_actions=["发布例外、密钥例外、合规签核和补偿控制应在发布前统一复核。"],
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
        "# v3.9 release gate and rollback governance pack（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- release_executed: `{payload['release_executed']}`",
        f"- rollback_executed: `{payload['rollback_executed']}`",
        f"- migration_executed: `{payload['migration_executed']}`",
        f"- tag_created: `{payload['tag_created']}`",
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


def build_release_gate_rollback_governance_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(RELEASE_OPT_IN_KEYS + RELEASE_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.9.0",
        "phase": "v3.9 Phase 19.3",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "service_started": False,
        "online_endpoints_called": False,
        "external_system_connected": False,
        "release_executed": False,
        "rollback_executed": False,
        "migration_executed": False,
        "docker_build_executed": False,
        "tag_created": False,
        "github_release_created": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(RELEASE_OPT_IN_KEYS + RELEASE_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "补充发布变更审批、发布窗口、冻结窗口、回滚窗口和发布负责人记录。",
            "补充真实 rollback drill、migration rollback、配置回滚和外部集成降级证据。",
            "保持默认只读，不把 release review 或 runbook 视为生产发布批准。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_release_gate_rollback_governance_pack"
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
        "release_executed": payload["release_executed"],
        "rollback_executed": payload["rollback_executed"],
        "migration_executed": payload["migration_executed"],
        "tag_created": payload["tag_created"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.9 release gate and rollback governance pack（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_release_gate_rollback_governance_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
