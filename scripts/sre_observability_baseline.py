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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "sre_observability_baseline"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

SRE_OPT_IN_KEYS = [
    "SRE_OBSERVABILITY_ENABLED",
    "SRE_APM_ENABLED",
    "SRE_ALERTING_ENABLED",
    "SRE_BACKUP_DRILL_ENABLED",
    "SRE_DR_DRILL_ENABLED",
    "SRE_CAPACITY_TEST_ENABLED",
]

SRE_CONFIG_KEYS = [
    "SRE_APM_PROVIDER",
    "SRE_LOG_SINK",
    "SRE_ALERT_CHANNEL",
    "SRE_ONCALL_ROTATION",
    "SRE_RTO_MINUTES",
    "SRE_RPO_MINUTES",
]

BOUNDARY_DECLARATIONS = [
    "只读 SRE observability baseline",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务",
    "不访问在线 /health、/metrics、/operations 或 /runtime/snapshot 端点",
    "不连接真实 APM、日志平台、告警平台或值班系统",
    "不执行真实压测、备份恢复或灾备切换",
    "不删除用户数据，不自动清理报告，不修改 .env",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文",
    "不把本地 metrics store、只读脚本或 runbook 视为企业级 SRE 验收完成",
    "不宣称 RTO/RPO、SLO/SLI、容量上限或告警触发能力已生产验收完成",
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
        "metrics_api": "app/api/metrics.py",
        "runtime_snapshot_api": "app/api/runtime_snapshot.py",
        "operations_api": "app/api/operations.py",
        "audit_api": "app/api/audit.py",
        "metrics_recorder": "app/harness/metrics/runtime_metrics.py",
        "sqlite_metrics_store": "app/harness/metrics/metrics_store.py",
        "postgres_metrics_store": "app/storage/postgres/metrics_store.py",
        "audit_store": "app/storage/audit_store.py",
        "postgres_audit_store": "app/storage/postgres/audit_store.py",
        "structured_logging": "app/core/structured_logging.py",
        "request_logging": "app/core/request_logging.py",
        "acceptance_snapshot_script": "scripts/acceptance_snapshot.py",
        "failure_diagnostics_script": "scripts/failure_diagnostics.py",
        "demo_artifact_bundle_script": "scripts/demo_artifact_bundle.py",
        "evidence_archive_manifest_script": "scripts/evidence_archive_manifest.py",
        "backup_restore_checklist": "docs/backup_restore_checklist_v31.md",
        "operations_troubleshooting_index": "docs/operations_troubleshooting_index_v31.md",
        "operations_monitoring_backup_drill": "docs/operations_monitoring_backup_drill_v30.md",
        "failure_diagnostics_runbook": "docs/failure_diagnostics_pack_v32.md",
        "deployment_runbook": "docs/deployment_runbook.md",
        "metrics_tests": "tests/test_runtime_persistence_v05.py",
        "runtime_tests": "tests/test_runtime_hardening_v055.py",
        "operations_summary_tests": "tests/test_operations_summary_v312.py",
        "audit_tests": "tests/test_audit_v045.py",
        "audit_retention_tests": "tests/test_audit_retention_export_v74.py",
        "failure_diagnostics_tests": "tests/test_failure_diagnostics_v324.py",
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
    metrics_required = ["metrics_api", "metrics_recorder", "sqlite_metrics_store", "postgres_metrics_store", "metrics_tests"]
    runtime_required = ["runtime_snapshot_api", "runtime_tests"]
    operations_required = ["operations_api", "operations_summary_tests", "acceptance_snapshot_script", "demo_artifact_bundle_script"]
    audit_required = ["audit_api", "audit_store", "postgres_audit_store", "audit_tests", "audit_retention_tests"]
    logging_required = ["structured_logging", "request_logging"]
    diagnostics_required = ["failure_diagnostics_script", "failure_diagnostics_runbook", "failure_diagnostics_tests"]
    runbook_required = ["backup_restore_checklist", "operations_troubleshooting_index", "operations_monitoring_backup_drill", "deployment_runbook"]

    return [
        _check(
            "runtime_metrics_and_cost_api",
            status="partial" if not _missing_local(local, metrics_required) else "skipped",
            missing_conditions=_missing_local(local, metrics_required),
            evidence={key: local[key] for key in metrics_required if key in local},
            risk_notes=["本地 metrics store 不等于企业级 APM；仍需外部 APM/Tracing 方案验收。"],
        ),
        _check(
            "runtime_snapshot_api",
            status="partial" if not _missing_local(local, runtime_required) else "skipped",
            missing_conditions=_missing_local(local, runtime_required),
            evidence={key: local[key] for key in runtime_required if key in local},
            recommended_actions=["后续 SRE 接管时需定义 snapshot 字段稳定性、查询权限和失败路径告警。"],
        ),
        _check(
            "operations_summary_and_acceptance_evidence",
            status="partial" if not _missing_local(local, operations_required) else "skipped",
            missing_conditions=_missing_local(local, operations_required),
            evidence={key: local[key] for key in operations_required if key in local},
            risk_notes=["operations summary 是只读运营总览，不等于集中观测平台。"],
        ),
        _check(
            "audit_export_and_redaction",
            status="partial" if not _missing_local(local, audit_required) else "skipped",
            missing_conditions=_missing_local(local, audit_required),
            evidence={key: local[key] for key in audit_required if key in local},
            recommended_actions=["SRE/审计联动需定义审计留存、导出授权、脱敏字段和证据链完整性。"],
        ),
        _check(
            "structured_logging_boundary",
            status="partial" if not _missing_local(local, logging_required) else "skipped",
            missing_conditions=_missing_local(local, logging_required),
            evidence={key: local[key] for key in logging_required if key in local},
            risk_notes=["结构化日志已具备本地边界，但仍需集中日志 sink、留存和查询权限验收。"],
        ),
        _check(
            "failure_diagnostics_pack",
            status="partial" if not _missing_local(local, diagnostics_required) else "skipped",
            missing_conditions=_missing_local(local, diagnostics_required),
            evidence={key: local[key] for key in diagnostics_required if key in local},
            recommended_actions=["后续需把故障诊断与告警触发、on-call 升级路径、incident 复盘闭环串联。"],
        ),
        _check(
            "backup_restore_and_dr_runbooks",
            status="partial" if not _missing_local(local, runbook_required) else "skipped",
            missing_conditions=_missing_local(local, runbook_required),
            evidence={key: local[key] for key in runbook_required if key in local},
            risk_notes=["当前为 runbook 级材料，不等于真实 RTO/RPO 或 DR 切换验收完成。"],
        ),
        _check(
            "external_apm_tracing_readiness",
            status="partial" if _env_enabled("SRE_APM_ENABLED") else "skipped",
            missing_conditions=[] if _env_enabled("SRE_APM_ENABLED") else ["opt_in:SRE_APM_ENABLED_not_enabled"],
            evidence={
                "env": _env_presence(["SRE_APM_ENABLED", "SRE_APM_PROVIDER", "SRE_LOG_SINK"]),
                "external_apm_connected": False,
                "trace_export_executed": False,
            },
            risk_notes=["不连接真实 APM/Tracing；缺少 opt-in 时必须 skipped。"],
        ),
        _check(
            "alerting_slo_oncall_readiness",
            status="partial" if _env_enabled("SRE_ALERTING_ENABLED") else "skipped",
            missing_conditions=[] if _env_enabled("SRE_ALERTING_ENABLED") else ["opt_in:SRE_ALERTING_ENABLED_not_enabled"],
            evidence={
                "env": _env_presence(["SRE_ALERTING_ENABLED", "SRE_ALERT_CHANNEL", "SRE_ONCALL_ROTATION"]),
                "alert_sent": False,
                "oncall_notified": False,
            },
            risk_notes=["不触发真实告警；SLO/SLI、告警分级和值班响应仍需人工受控验收。"],
        ),
        _check(
            "capacity_backup_dr_drill_gaps",
            status="skipped",
            missing_conditions=[
                "evidence:capacity_test_report_missing",
                "evidence:backup_restore_drill_missing",
                "evidence:dr_failover_drill_missing",
                "evidence:rto_rpo_attainment_missing",
            ],
            evidence={
                "env": _env_presence(["SRE_CAPACITY_TEST_ENABLED", "SRE_BACKUP_DRILL_ENABLED", "SRE_DR_DRILL_ENABLED", "SRE_RTO_MINUTES", "SRE_RPO_MINUTES"]),
                "capacity_test_executed": False,
                "backup_restore_executed": False,
                "dr_failover_executed": False,
            },
            recommended_actions=["后续 Phase 18.x 需补容量压测、备份恢复、灾备切换与 RTO/RPO 达成证据。"],
        ),
    ]


def _derive_status(checks: list[dict[str, Any]], local: dict[str, dict[str, Any]]) -> str:
    if any(check["status"] == "blocked" for check in checks):
        return "blocked"
    if any(not item["present"] for item in local.values()):
        return "skipped"
    if any(check["status"] == "skipped" for check in checks):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.8 SRE observability baseline（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- external_apm_connected: {payload.get('external_apm_connected', False)}",
        f"- alert_sent: {payload.get('alert_sent', False)}",
        f"- capacity_test_executed: {payload.get('capacity_test_executed', False)}",
        f"- backup_restore_executed: {payload.get('backup_restore_executed', False)}",
        f"- dr_failover_executed: {payload.get('dr_failover_executed', False)}",
        "",
        "## 检查项",
    ]
    for check in payload.get("acceptance_checks", []):
        lines.extend(
            [
                f"### {check['check_id']}",
                f"- status: {check['status']}",
                f"- missing_conditions: {json.dumps(check.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_sre_observability_baseline(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    local = _local_checks()
    checks = _acceptance_checks(local)
    missing_conditions = sorted({item for check in checks for item in check.get("missing_conditions", [])})
    status = _derive_status(checks, local)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.8.0",
        "phase": "v3.8 Phase 18.1",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "online_endpoints_called": False,
        "external_apm_connected": False,
        "log_sink_connected": False,
        "alert_sent": False,
        "oncall_notified": False,
        "capacity_test_executed": False,
        "backup_restore_executed": False,
        "dr_failover_executed": False,
        "secret_plaintext_output": False,
        "env": _env_presence(SRE_OPT_IN_KEYS + SRE_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "Phase 18.2 可继续推进 SLO/SLI and alerting runbook pack。",
            "后续需补真实 APM/Tracing、集中日志、告警触发、容量压测、备份恢复和 DR 切换的人工受控验收证据。",
            "继续保持默认 fake/offline，不把本地 metrics store 或 runbook 视为企业级 SRE 验收完成。",
        ],
        "output_dir": str(output_root),
    }
    if _contains_secret_like_text(json.dumps(payload, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_sre_observability_baseline"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "online_endpoints_called": False,
        "external_apm_connected": False,
        "alert_sent": False,
        "capacity_test_executed": False,
        "backup_restore_executed": False,
        "dr_failover_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "check_count": len(checks),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.8 SRE observability baseline（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_sre_observability_baseline(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
