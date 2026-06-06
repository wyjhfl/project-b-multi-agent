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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "slo_alerting_runbook"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"https?://[^/\s]+:[^@\s]+@"),
]

ALERT_OPT_IN_KEYS = [
    "SRE_ALERTING_ENABLED",
    "SRE_SLO_REVIEW_ENABLED",
    "SRE_ALERT_DRY_RUN_ENABLED",
    "SRE_ONCALL_DRILL_ENABLED",
]

ALERT_CONFIG_KEYS = [
    "SRE_ALERT_CHANNEL",
    "SRE_ONCALL_ROTATION",
    "SRE_ESCALATION_POLICY",
    "SRE_SLO_AVAILABILITY_TARGET",
    "SRE_SLO_LATENCY_P95_MS",
    "SRE_SLO_ERROR_RATE_PERCENT",
    "SRE_ALERT_WEBHOOK",
]

BOUNDARY_DECLARATIONS = [
    "只读 SLO/SLI and alerting runbook pack",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务",
    "不访问在线 /health、/metrics、/operations 或 /runtime/snapshot 端点",
    "不连接真实 APM、日志平台、告警平台或值班系统",
    "不发送真实告警，不通知真实 on-call，不执行真实 incident 升级",
    "不执行真实压测、备份恢复或灾备切换",
    "不修改 .env，不删除用户数据，不自动清理报告",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码或告警 webhook 原文",
    "不把 runbook、placeholder env 或本地 metrics store 宣称为企业级 SLO/告警验收完成",
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
        "structured_logging": "app/core/structured_logging.py",
        "request_logging": "app/core/request_logging.py",
        "runtime_metrics_recorder": "app/harness/metrics/runtime_metrics.py",
        "acceptance_snapshot_script": "scripts/acceptance_snapshot.py",
        "failure_diagnostics_script": "scripts/failure_diagnostics.py",
        "sre_baseline_script": "scripts/sre_observability_baseline.py",
        "operations_troubleshooting_runbook": "docs/operations_troubleshooting_index_v31.md",
        "failure_diagnostics_runbook": "docs/failure_diagnostics_pack_v32.md",
        "sre_baseline_runbook": "docs/sre_observability_baseline_v38.md",
        "deployment_runbook": "docs/deployment_runbook.md",
        "metrics_tests": "tests/test_runtime_persistence_v05.py",
        "operations_tests": "tests/test_operations_summary_v312.py",
        "failure_diagnostics_tests": "tests/test_failure_diagnostics_v324.py",
        "sre_baseline_tests": "tests/test_sre_observability_baseline_v381.py",
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
    slo_source_required = ["metrics_api", "runtime_snapshot_api", "operations_api", "runtime_metrics_recorder"]
    logging_required = ["structured_logging", "request_logging"]
    evidence_required = ["acceptance_snapshot_script", "failure_diagnostics_script", "sre_baseline_script"]
    runbook_required = [
        "operations_troubleshooting_runbook",
        "failure_diagnostics_runbook",
        "sre_baseline_runbook",
        "deployment_runbook",
    ]
    tests_required = ["metrics_tests", "operations_tests", "failure_diagnostics_tests", "sre_baseline_tests"]

    alerting_missing = []
    if not _env_enabled("SRE_ALERTING_ENABLED"):
        alerting_missing.append("opt_in:SRE_ALERTING_ENABLED_not_enabled")
    if not os.getenv("SRE_ALERT_CHANNEL"):
        alerting_missing.append("env:SRE_ALERT_CHANNEL_missing")
    if not os.getenv("SRE_ONCALL_ROTATION"):
        alerting_missing.append("env:SRE_ONCALL_ROTATION_missing")

    dry_run_missing = []
    if not _env_enabled("SRE_ALERT_DRY_RUN_ENABLED"):
        dry_run_missing.append("opt_in:SRE_ALERT_DRY_RUN_ENABLED_not_enabled")
    dry_run_missing.append("evidence:alert_dry_run_report_missing")

    oncall_missing = []
    if not _env_enabled("SRE_ONCALL_DRILL_ENABLED"):
        oncall_missing.append("opt_in:SRE_ONCALL_DRILL_ENABLED_not_enabled")
    oncall_missing.append("evidence:oncall_escalation_drill_report_missing")

    return [
        _check(
            "slo_sli_source_inventory",
            status="partial" if not _missing_local(local, slo_source_required) else "skipped",
            missing_conditions=_missing_local(local, slo_source_required),
            evidence={key: local[key] for key in slo_source_required if key in local},
            risk_notes=["当前仅盘点本地指标来源，不等于 SLO/SLI 已被企业监控平台采集。"],
        ),
        _check(
            "slo_target_configuration",
            status="partial" if _env_enabled("SRE_SLO_REVIEW_ENABLED") else "skipped",
            missing_conditions=[] if _env_enabled("SRE_SLO_REVIEW_ENABLED") else ["opt_in:SRE_SLO_REVIEW_ENABLED_not_enabled"],
            evidence={
                "env": _env_presence(
                    [
                        "SRE_SLO_REVIEW_ENABLED",
                        "SRE_SLO_AVAILABILITY_TARGET",
                        "SRE_SLO_LATENCY_P95_MS",
                        "SRE_SLO_ERROR_RATE_PERCENT",
                    ]
                )
            },
            recommended_actions=["后续需由业务方和 SRE 共同确认 availability、latency、error-rate 目标和错误预算口径。"],
        ),
        _check(
            "structured_logging_for_alert_context",
            status="partial" if not _missing_local(local, logging_required) else "skipped",
            missing_conditions=_missing_local(local, logging_required),
            evidence={key: local[key] for key in logging_required if key in local},
            risk_notes=["结构化日志可作为告警上下文来源，但仍需集中日志 sink、查询权限和留存策略验收。"],
        ),
        _check(
            "alert_severity_and_routing",
            status="partial" if not alerting_missing else "skipped",
            missing_conditions=alerting_missing,
            evidence={
                "env": _env_presence(["SRE_ALERTING_ENABLED", "SRE_ALERT_CHANNEL", "SRE_ESCALATION_POLICY"]),
                "alert_sent": False,
            },
            recommended_actions=["后续需定义 P0/P1/P2 分级、静默窗口、重复告警抑制和人工升级路径。"],
        ),
        _check(
            "oncall_and_escalation_readiness",
            status="partial" if not oncall_missing else "skipped",
            missing_conditions=oncall_missing,
            evidence={
                "env": _env_presence(["SRE_ONCALL_DRILL_ENABLED", "SRE_ONCALL_ROTATION", "SRE_ESCALATION_POLICY"]),
                "oncall_notified": False,
            },
            risk_notes=["当前不通知真实值班人员；缺少演练报告时必须保持 skipped。"],
        ),
        _check(
            "alert_dry_run_evidence",
            status="partial" if not dry_run_missing else "skipped",
            missing_conditions=dry_run_missing,
            evidence={
                "env": _env_presence(["SRE_ALERT_DRY_RUN_ENABLED", "SRE_ALERT_CHANNEL"]),
                "alert_sent": False,
                "alert_webhook_called": False,
            },
            risk_notes=["当前不调用 webhook，不发送真实告警；dry-run 报告缺失时不得伪造成成功。"],
        ),
        _check(
            "incident_runbook_linkage",
            status="partial" if not _missing_local(local, runbook_required) else "skipped",
            missing_conditions=_missing_local(local, runbook_required),
            evidence={key: local[key] for key in runbook_required if key in local},
            recommended_actions=["后续需把告警分级与 incident runbook、failure diagnostics、postmortem 模板串联。"],
        ),
        _check(
            "evidence_generation_scripts",
            status="partial" if not _missing_local(local, evidence_required) else "skipped",
            missing_conditions=_missing_local(local, evidence_required),
            evidence={key: local[key] for key in evidence_required if key in local},
            risk_notes=["证据脚本只生成本地只读报告，不替代真实告警触发和 on-call 响应证据。"],
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
        "# v3.8 SLO/SLI and alerting runbook pack（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- alert_sent: `{payload['alert_sent']}`",
        f"- oncall_notified: `{payload['oncall_notified']}`",
        f"- alert_webhook_called: `{payload['alert_webhook_called']}`",
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


def build_slo_alerting_runbook_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(ALERT_OPT_IN_KEYS + ALERT_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.8.0",
        "phase": "v3.8 Phase 18.2",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "online_endpoints_called": False,
        "service_started": False,
        "external_apm_connected": False,
        "log_sink_connected": False,
        "alert_sent": False,
        "oncall_notified": False,
        "alert_webhook_called": False,
        "incident_escalation_executed": False,
        "capacity_test_executed": False,
        "backup_restore_executed": False,
        "dr_failover_executed": False,
        "secret_plaintext_output": False,
        "env": _env_presence(ALERT_OPT_IN_KEYS + ALERT_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "由业务方与 SRE 确认 availability、latency、error-rate 和错误预算目标。",
            "补充真实告警 dry-run 证据、on-call 升级演练记录和 incident runbook 复盘模板。",
            "保持默认 fake/offline，不把本地 runbook 或 placeholder env 视为企业级告警验收完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_slo_alerting_runbook_pack"
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
        "alert_sent": payload["alert_sent"],
        "oncall_notified": payload["oncall_notified"],
        "alert_webhook_called": payload["alert_webhook_called"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.8 SLO/SLI and alerting runbook pack（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_slo_alerting_runbook_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
