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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "backup_restore_dr_evidence"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

DR_OPT_IN_KEYS = [
    "SRE_BACKUP_DRILL_ENABLED",
    "SRE_RESTORE_DRY_RUN_ENABLED",
    "SRE_DR_DRILL_ENABLED",
]

DR_CONFIG_KEYS = [
    "SRE_RTO_MINUTES",
    "SRE_RPO_MINUTES",
    "SRE_BACKUP_SCOPE",
    "SRE_BACKUP_TARGET",
    "SRE_DR_SECONDARY_REGION",
    "DATABASE_URL",
    "REDIS_URL",
]

BOUNDARY_DECLARATIONS = [
    "只读 backup/restore and DR drill evidence pack",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务",
    "不连接真实 PostgreSQL、Redis、对象存储、IdP、LLM provider 或外部 MCP",
    "不执行真实备份，不执行真实恢复，不执行灾备切换",
    "不执行 Alembic migration，不写业务数据、审计数据或指标数据",
    "不删除用户数据，不移动或清理报告，不修改 .env",
    "不读取或输出真实 secret、token、API key、client_secret、DATABASE_URL、REDIS_URL 或对象存储凭证原文",
    "不把 runbook、placeholder env 或本地 SQLite 文件宣称为 RTO/RPO 或 DR 生产验收完成",
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
        "sqlite_demo_db_script": "scripts/init_demo_db.py",
        "demo_seed_script": "scripts/demo_seed_data.py",
        "sqlite_metrics_store": "app/harness/metrics/metrics_store.py",
        "sqlite_audit_store": "app/storage/audit_store.py",
        "postgres_task_store": "app/storage/postgres/task_store.py",
        "postgres_audit_store": "app/storage/postgres/audit_store.py",
        "postgres_metrics_store": "app/storage/postgres/metrics_store.py",
        "alembic_env": "alembic/env.py",
        "docker_compose": "docker-compose.yml",
        "docker_compose_prod": "docker-compose.prod.yml",
        "deployment_guard": "app/core/deployment_guard.py",
        "backup_restore_checklist": "docs/backup_restore_checklist_v31.md",
        "operations_monitoring_backup_drill": "docs/operations_monitoring_backup_drill_v30.md",
        "deployment_runbook": "docs/deployment_runbook.md",
        "failure_diagnostics_runbook": "docs/failure_diagnostics_pack_v32.md",
        "store_redis_readiness_drill": "scripts/store_redis_readiness_drill.py",
        "failure_diagnostics_script": "scripts/failure_diagnostics.py",
        "evidence_archive_manifest_script": "scripts/evidence_archive_manifest.py",
        "storage_tests": "tests/test_storage_v20.py",
        "runtime_persistence_tests": "tests/test_runtime_persistence_v05.py",
        "audit_tests": "tests/test_audit_v045.py",
        "store_redis_tests": "tests/test_store_redis_readiness_drill_v374.py",
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
    storage_required = [
        "sqlite_demo_db_script",
        "sqlite_metrics_store",
        "sqlite_audit_store",
        "postgres_task_store",
        "postgres_audit_store",
        "postgres_metrics_store",
    ]
    deployment_required = ["alembic_env", "docker_compose", "docker_compose_prod", "deployment_guard"]
    runbook_required = [
        "backup_restore_checklist",
        "operations_monitoring_backup_drill",
        "deployment_runbook",
        "failure_diagnostics_runbook",
    ]
    evidence_required = ["store_redis_readiness_drill", "failure_diagnostics_script", "evidence_archive_manifest_script"]
    tests_required = ["storage_tests", "runtime_persistence_tests", "audit_tests", "store_redis_tests"]

    rto_rpo_missing = []
    if not os.getenv("SRE_RTO_MINUTES"):
        rto_rpo_missing.append("env:SRE_RTO_MINUTES_missing")
    if not os.getenv("SRE_RPO_MINUTES"):
        rto_rpo_missing.append("env:SRE_RPO_MINUTES_missing")

    backup_missing = []
    if not _env_enabled("SRE_BACKUP_DRILL_ENABLED"):
        backup_missing.append("opt_in:SRE_BACKUP_DRILL_ENABLED_not_enabled")
    backup_missing.append("evidence:backup_drill_report_missing")

    restore_missing = []
    if not _env_enabled("SRE_RESTORE_DRY_RUN_ENABLED"):
        restore_missing.append("opt_in:SRE_RESTORE_DRY_RUN_ENABLED_not_enabled")
    restore_missing.append("evidence:restore_dry_run_report_missing")

    dr_missing = []
    if not _env_enabled("SRE_DR_DRILL_ENABLED"):
        dr_missing.append("opt_in:SRE_DR_DRILL_ENABLED_not_enabled")
    dr_missing.append("evidence:dr_failover_report_missing")

    return [
        _check(
            "backup_scope_inventory",
            status="partial" if not _missing_local(local, storage_required) else "skipped",
            missing_conditions=_missing_local(local, storage_required),
            evidence={key: local[key] for key in storage_required if key in local},
            risk_notes=["当前仅盘点 SQLite/PostgreSQL store 与 demo 数据入口，不执行真实备份。"],
        ),
        _check(
            "deployment_and_migration_boundary",
            status="partial" if not _missing_local(local, deployment_required) else "skipped",
            missing_conditions=_missing_local(local, deployment_required),
            evidence={key: local[key] for key in deployment_required if key in local},
            risk_notes=["本阶段不执行 Alembic migration，也不连接真实数据库。"],
        ),
        _check(
            "rto_rpo_target_presence",
            status="partial" if not rto_rpo_missing else "skipped",
            missing_conditions=rto_rpo_missing,
            evidence={"env": _env_presence(["SRE_RTO_MINUTES", "SRE_RPO_MINUTES"])},
            recommended_actions=["后续需由业务方和 SRE 确认每类数据的 RTO/RPO，并形成演练达成证据。"],
        ),
        _check(
            "backup_drill_evidence",
            status="partial" if not backup_missing else "skipped",
            missing_conditions=backup_missing,
            evidence={
                "env": _env_presence(["SRE_BACKUP_DRILL_ENABLED", "SRE_BACKUP_SCOPE", "SRE_BACKUP_TARGET"]),
                "backup_executed": False,
            },
            risk_notes=["缺少真实备份演练报告时必须 skipped，不得把 runbook 视为备份成功。"],
        ),
        _check(
            "restore_dry_run_evidence",
            status="partial" if not restore_missing else "skipped",
            missing_conditions=restore_missing,
            evidence={
                "env": _env_presence(["SRE_RESTORE_DRY_RUN_ENABLED", "SRE_BACKUP_TARGET"]),
                "restore_executed": False,
            },
            risk_notes=["缺少恢复 dry-run 报告时必须 skipped，不得宣称 RTO/RPO 达成。"],
        ),
        _check(
            "dr_failover_evidence",
            status="partial" if not dr_missing else "skipped",
            missing_conditions=dr_missing,
            evidence={
                "env": _env_presence(["SRE_DR_DRILL_ENABLED", "SRE_DR_SECONDARY_REGION"]),
                "dr_failover_executed": False,
            },
            risk_notes=["缺少 DR 切换演练报告时必须 skipped，不得宣称灾备验收完成。"],
        ),
        _check(
            "runbook_and_failure_diagnostics_linkage",
            status="partial" if not _missing_local(local, runbook_required) else "skipped",
            missing_conditions=_missing_local(local, runbook_required),
            evidence={key: local[key] for key in runbook_required if key in local},
            recommended_actions=["后续需把备份恢复、故障诊断、部署回滚和 postmortem 记录串联。"],
        ),
        _check(
            "evidence_generation_scripts",
            status="partial" if not _missing_local(local, evidence_required) else "skipped",
            missing_conditions=_missing_local(local, evidence_required),
            evidence={key: local[key] for key in evidence_required if key in local},
        ),
        _check(
            "regression_test_coverage",
            status="partial" if not _missing_local(local, tests_required) else "skipped",
            missing_conditions=_missing_local(local, tests_required),
            evidence={key: local[key] for key in tests_required if key in local},
        ),
    ]


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.8 backup/restore and DR drill evidence pack（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- backup_executed: `{payload['backup_executed']}`",
        f"- restore_executed: `{payload['restore_executed']}`",
        f"- dr_failover_executed: `{payload['dr_failover_executed']}`",
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


def build_backup_restore_dr_evidence_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(DR_OPT_IN_KEYS + DR_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.8.0",
        "phase": "v3.8 Phase 18.3",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "online_endpoints_called": False,
        "service_started": False,
        "database_connected": False,
        "redis_connected": False,
        "object_store_connected": False,
        "migration_executed": False,
        "backup_executed": False,
        "restore_executed": False,
        "dr_failover_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(DR_OPT_IN_KEYS + DR_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "确认 PostgreSQL、SQLite demo、审计、指标、报告和配置模板的备份范围。",
            "补充真实备份演练、恢复 dry-run、DR 切换演练和 RTO/RPO 达成证据。",
            "保持默认 fake/offline，不把 runbook 或本地 SQLite 文件视为生产 DR 验收完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_backup_restore_dr_evidence_pack"
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
        "database_connected": payload["database_connected"],
        "redis_connected": payload["redis_connected"],
        "backup_executed": payload["backup_executed"],
        "restore_executed": payload["restore_executed"],
        "dr_failover_executed": payload["dr_failover_executed"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.8 backup/restore and DR drill evidence pack（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_backup_restore_dr_evidence_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
