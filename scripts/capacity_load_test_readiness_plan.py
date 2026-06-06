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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "capacity_load_test_readiness"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

CAPACITY_OPT_IN_KEYS = [
    "SRE_CAPACITY_TEST_ENABLED",
    "SRE_LOAD_TEST_DRY_RUN_ENABLED",
    "SRE_SOAK_TEST_ENABLED",
]

CAPACITY_CONFIG_KEYS = [
    "SRE_TARGET_CONCURRENCY",
    "SRE_TARGET_RPS",
    "SRE_TARGET_P95_LATENCY_MS",
    "SRE_TARGET_ERROR_RATE_PERCENT",
    "SRE_TEST_DURATION_MINUTES",
    "SRE_CAPACITY_TEST_BASE_URL",
]

BOUNDARY_DECLARATIONS = [
    "只读 capacity and load-test readiness plan",
    "仅检查 env name、present 布尔状态、本地代码文件、测试文件和 runbook 文件存在性",
    "不启动服务，不访问在线端点",
    "不执行真实压测、soak test、并发请求或容量探测",
    "不连接真实 PostgreSQL、Redis、APM、日志平台、告警平台、IdP、LLM provider、外部 MCP 或业务系统",
    "不写业务数据、审计数据或指标数据",
    "不删除用户数据，不清理报告，不修改 .env",
    "不读取或输出真实 secret、token、API key、client_secret、连接串密码或压测目标 URL 原文",
    "不把 runbook、placeholder env 或本地测试通过宣称为生产容量上限验收完成",
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
        "health_api": "app/main.py",
        "metrics_api": "app/api/metrics.py",
        "runtime_snapshot_api": "app/api/runtime_snapshot.py",
        "operations_api": "app/api/operations.py",
        "tasks_api": "app/api/tasks.py",
        "tools_api": "app/api/tools.py",
        "nl2sql_api": "app/api/nl2sql.py",
        "approvals_api": "app/api/approvals.py",
        "request_size_limit": "app/core/request_guards.py",
        "rate_limit": "app/core/request_guards.py",
        "abuse_guard": "app/core/request_guards.py",
        "structured_logging": "app/core/structured_logging.py",
        "runtime_metrics_recorder": "app/harness/metrics/runtime_metrics.py",
        "failure_diagnostics_script": "scripts/failure_diagnostics.py",
        "sre_baseline_script": "scripts/sre_observability_baseline.py",
        "slo_alerting_script": "scripts/slo_alerting_runbook_pack.py",
        "backup_dr_script": "scripts/backup_restore_dr_evidence_pack.py",
        "deployment_runbook": "docs/deployment_runbook.md",
        "sre_baseline_runbook": "docs/sre_observability_baseline_v38.md",
        "slo_alerting_runbook": "docs/slo_alerting_runbook_pack_v38.md",
        "backup_dr_runbook": "docs/backup_restore_dr_evidence_pack_v38.md",
        "runtime_tests": "tests/test_runtime_hardening_v055.py",
        "request_guard_tests": "tests/test_request_guards_v72.py",
        "operations_tests": "tests/test_operations_summary_v312.py",
        "metrics_tests": "tests/test_runtime_persistence_v05.py",
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
    endpoint_required = ["health_api", "metrics_api", "runtime_snapshot_api", "operations_api", "tasks_api", "tools_api", "nl2sql_api", "approvals_api"]
    guard_required = ["request_size_limit", "rate_limit", "abuse_guard"]
    observability_required = ["structured_logging", "runtime_metrics_recorder", "metrics_api", "failure_diagnostics_script"]
    runbook_required = ["deployment_runbook", "sre_baseline_runbook", "slo_alerting_runbook", "backup_dr_runbook"]
    test_required = ["runtime_tests", "request_guard_tests", "operations_tests", "metrics_tests"]

    target_missing = []
    for key in ["SRE_TARGET_CONCURRENCY", "SRE_TARGET_RPS", "SRE_TARGET_P95_LATENCY_MS", "SRE_TARGET_ERROR_RATE_PERCENT"]:
        if not os.getenv(key):
            target_missing.append(f"env:{key}_missing")

    load_missing = []
    if not _env_enabled("SRE_CAPACITY_TEST_ENABLED"):
        load_missing.append("opt_in:SRE_CAPACITY_TEST_ENABLED_not_enabled")
    if not _env_enabled("SRE_LOAD_TEST_DRY_RUN_ENABLED"):
        load_missing.append("opt_in:SRE_LOAD_TEST_DRY_RUN_ENABLED_not_enabled")
    load_missing.append("evidence:load_test_plan_or_report_missing")

    soak_missing = []
    if not _env_enabled("SRE_SOAK_TEST_ENABLED"):
        soak_missing.append("opt_in:SRE_SOAK_TEST_ENABLED_not_enabled")
    soak_missing.append("evidence:soak_test_report_missing")

    return [
        _check(
            "critical_endpoint_inventory",
            status="partial" if not _missing_local(local, endpoint_required) else "skipped",
            missing_conditions=_missing_local(local, endpoint_required),
            evidence={key: local[key] for key in endpoint_required if key in local},
            risk_notes=["当前仅盘点关键 API 入口，不对在线端点发起请求。"],
        ),
        _check(
            "traffic_model_targets",
            status="partial" if not target_missing else "skipped",
            missing_conditions=target_missing,
            evidence={
                "env": _env_presence(
                    [
                        "SRE_TARGET_CONCURRENCY",
                        "SRE_TARGET_RPS",
                        "SRE_TARGET_P95_LATENCY_MS",
                        "SRE_TARGET_ERROR_RATE_PERCENT",
                        "SRE_TEST_DURATION_MINUTES",
                    ]
                )
            },
            recommended_actions=["后续需按企业内网试点用户数、峰值 RPS、长任务比例、工具调用比例和 NL2SQL 比例定义流量模型。"],
        ),
        _check(
            "request_guard_and_abuse_controls",
            status="partial" if not _missing_local(local, guard_required) else "skipped",
            missing_conditions=_missing_local(local, guard_required),
            evidence={key: local[key] for key in guard_required if key in local},
            risk_notes=["当前为本地 guard 文件存在性检查，不等于网关级或多实例限流生产验收。"],
        ),
        _check(
            "observability_for_capacity_test",
            status="partial" if not _missing_local(local, observability_required) else "skipped",
            missing_conditions=_missing_local(local, observability_required),
            evidence={key: local[key] for key in observability_required if key in local},
            recommended_actions=["真实压测前需定义采集窗口、指标粒度、日志关联字段、告警阈值和成本上限。"],
        ),
        _check(
            "load_test_dry_run_evidence",
            status="partial" if not load_missing else "skipped",
            missing_conditions=load_missing,
            evidence={
                "env": _env_presence(["SRE_CAPACITY_TEST_ENABLED", "SRE_LOAD_TEST_DRY_RUN_ENABLED", "SRE_CAPACITY_TEST_BASE_URL"]),
                "load_test_executed": False,
            },
            risk_notes=["缺少压测计划或 dry-run 报告时必须 skipped，不得宣称容量上限已确认。"],
        ),
        _check(
            "soak_test_readiness",
            status="partial" if not soak_missing else "skipped",
            missing_conditions=soak_missing,
            evidence={
                "env": _env_presence(["SRE_SOAK_TEST_ENABLED", "SRE_TEST_DURATION_MINUTES"]),
                "soak_test_executed": False,
            },
            risk_notes=["缺少 soak test 报告时必须 skipped，不得宣称长期稳定性已验收。"],
        ),
        _check(
            "runbook_linkage",
            status="partial" if not _missing_local(local, runbook_required) else "skipped",
            missing_conditions=_missing_local(local, runbook_required),
            evidence={key: local[key] for key in runbook_required if key in local},
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
        "# v3.8 capacity and load-test readiness plan（只读）",
        "",
        f"- status: `{payload['status']}`",
        f"- version: `{payload['version']}`",
        f"- phase: `{payload['phase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- commit: `{payload['commit']}`",
        f"- load_test_executed: `{payload['load_test_executed']}`",
        f"- soak_test_executed: `{payload['soak_test_executed']}`",
        f"- online_endpoints_called: `{payload['online_endpoints_called']}`",
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


def build_capacity_load_test_readiness_plan(*, output_dir: str | Path | None = None) -> dict[str, Any]:
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
            _env_presence(CAPACITY_OPT_IN_KEYS + CAPACITY_CONFIG_KEYS),
            BOUNDARY_DECLARATIONS,
            acceptance_checks,
        ]
    )
    status = "blocked" if blocked_secret_output else ("skipped" if missing_conditions else "partial")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.8.0",
        "phase": "v3.8 Phase 18.4",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "service_started": False,
        "online_endpoints_called": False,
        "load_test_executed": False,
        "soak_test_executed": False,
        "capacity_probe_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_apm_connected": False,
        "alert_sent": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(CAPACITY_OPT_IN_KEYS + CAPACITY_CONFIG_KEYS),
        "local_checks": local,
        "acceptance_checks": acceptance_checks,
        "check_count": len(acceptance_checks),
        "missing_conditions": missing_conditions,
        "missing_count": len(missing_conditions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "定义企业内网试点流量模型、关键 API 权重、长任务比例、工具调用比例和 NL2SQL 比例。",
            "补充真实 load-test dry-run、soak test、指标采集、告警阈值和成本上限证据。",
            "保持默认 fake/offline，不把本地测试通过视为生产容量上限验收完成。",
        ],
    }
    if blocked_secret_output:
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"].append("blocked:secret_like_output_detected")
        payload["missing_count"] = len(payload["missing_conditions"])

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_capacity_load_test_readiness_plan"
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
        "load_test_executed": payload["load_test_executed"],
        "soak_test_executed": payload["soak_test_executed"],
        "database_connected": payload["database_connected"],
        "redis_connected": payload["redis_connected"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_path),
        "check_count": payload["check_count"],
        "missing_count": payload["missing_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 v3.8 capacity and load-test readiness plan（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = build_capacity_load_test_readiness_plan(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")


if __name__ == "__main__":
    main()
