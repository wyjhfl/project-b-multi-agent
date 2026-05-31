from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "incident_rehearsal"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

REAL_LLM_REQUIRED_ENV = [
    "REAL_LLM_SMOKE_ENABLED",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_PREFLIGHT_ENABLED",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    "REAL_LLM_MODEL",
    "REAL_LLM_API_KEY_ENV",
]

OIDC_REQUIRED_ENV = [
    "OIDC_ENABLED",
    "OIDC_ISSUER_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET_ENV",
    "OIDC_REDIRECT_URI",
]

PROD_REQUIRED_ENV = ["JWT_SECRET", "DATABASE_URL", "REDIS_URL"]

BOUNDARY_DECLARATIONS = [
    "默认 fake/offline",
    "默认 pytest/CI 不调用真实 LLM",
    "只读故障演练包",
    "默认不启动服务",
    "不修改环境变量或 .env",
    "不删除用户数据",
    "不自动清理报告",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
]

RECOMMENDED_RUNBOOKS = [
    "docs/failure_diagnostics_pack_v32.md",
    "docs/operations_troubleshooting_index_v31.md",
    "docs/operator_workflow_polish_v34.md",
    "docs/config_drift_checklist_v33.md",
    "docs/live_drill_window_v33.md",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _run_command(command: list[str], *, timeout: int = 20) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "return_code": proc.returncode,
            "stdout": proc.stdout.strip()[:4000],
            "stderr": proc.stderr.strip()[:4000],
        }
    except Exception as exc:
        return {"status": "skipped", "return_code": -1, "stdout": "", "stderr": type(exc).__name__}


def _read_json_url(url: str, timeout: float = 2.0) -> tuple[int, dict[str, Any] | None, str]:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": body[:1000]}
            return int(resp.status), payload if isinstance(payload, dict) else {"value": payload}, ""
    except URLError as exc:
        return 0, None, str(exc)
    except Exception as exc:
        return 0, None, str(exc)


def _present_env(keys: list[str]) -> tuple[list[str], dict[str, bool]]:
    details: dict[str, bool] = {}
    missing: list[str] = []
    for key in keys:
        present = bool(os.getenv(key))
        details[key] = present
        if not present:
            missing.append(key)
    return missing, details


def _real_llm_missing() -> tuple[list[str], dict[str, Any]]:
    missing, details = _present_env(REAL_LLM_REQUIRED_ENV)
    api_key_env_name = os.getenv("REAL_LLM_API_KEY_ENV", "").strip()
    target_present = bool(api_key_env_name and os.getenv(api_key_env_name))
    details["REAL_LLM_API_KEY_ENV_TARGET"] = target_present
    if not target_present:
        missing.append("REAL_LLM_API_KEY_ENV_TARGET")
    return missing, {"env_present": details, "real_llm_executed": False}


def _oidc_missing() -> tuple[list[str], dict[str, Any]]:
    missing, details = _present_env(OIDC_REQUIRED_ENV)
    secret_env_name = os.getenv("OIDC_CLIENT_SECRET_ENV", "").strip()
    target_present = bool(secret_env_name and os.getenv(secret_env_name))
    details["OIDC_CLIENT_SECRET_ENV_TARGET"] = target_present
    if not target_present:
        missing.append("OIDC_CLIENT_SECRET_ENV_TARGET")
    return missing, {"env_present": details}


def _latest_file(pattern: str) -> str:
    matches = sorted(ROOT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return ""
    try:
        return str(matches[0].resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return str(matches[0])


def _scenario(name: str, status: str, *, missing: list[str] | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "missing_conditions": missing or [],
        "evidence": evidence or {},
    }


def _build_scenarios(*, base_url: str, run_compose_checks: bool) -> tuple[list[dict[str, Any]], list[str]]:
    scenarios: list[dict[str, Any]] = []
    missing_conditions: list[str] = []

    def add_missing(item: str) -> None:
        if item not in missing_conditions:
            missing_conditions.append(item)

    health_status, health_payload, health_error = _read_json_url(base_url.rstrip("/") + "/health")
    if health_status == 0:
        add_missing("service_unavailable")
        scenarios.append(_scenario("service_unavailable", "skipped", missing=["service_unavailable"], evidence={"error": health_error}))
    else:
        scenarios.append(_scenario("service_unavailable", "success", evidence={"http_status": health_status, "health": health_payload}))

    if run_compose_checks:
        compose = _run_command(["docker", "compose", "config"])
        scenarios.append(_scenario("docker_compose_config_failure", compose["status"], evidence=compose))
        prod = _run_command(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml", "config"])
        scenarios.append(_scenario("prod_compose_missing_required_env", prod["status"], evidence=prod))
    else:
        add_missing("compose_checks_not_requested")
        scenarios.append(_scenario("docker_compose_config_failure", "skipped", missing=["compose_checks_not_requested"]))
        scenarios.append(_scenario("prod_compose_missing_required_env", "skipped", missing=["compose_checks_not_requested"]))

    prod_missing, prod_env = _present_env(PROD_REQUIRED_ENV)
    if prod_missing:
        for item in prod_missing:
            add_missing(f"prod_env:{item}")
    scenarios.append(
        _scenario(
            "prod_required_env_missing",
            "blocked" if prod_missing else "success",
            missing=prod_missing,
            evidence={"env_present": prod_env},
        )
    )

    dep_status, dep_payload, dep_error = _read_json_url(base_url.rstrip("/") + "/deployment/check")
    dep_failed = dep_status == 0 or bool(isinstance(dep_payload, dict) and dep_payload.get("ok") is False)
    if dep_status == 0:
        add_missing("deployment_check_unavailable")
    scenarios.append(
        _scenario(
            "deployment_check_ok_false",
            "skipped" if dep_status == 0 else ("failed" if dep_failed else "success"),
            missing=["deployment_check_unavailable"] if dep_status == 0 else [],
            evidence={"http_status": dep_status, "payload": dep_payload, "error": dep_error},
        )
    )

    ops_status, ops_payload, ops_error = _read_json_url(base_url.rstrip("/") + "/operations/summary")
    ops_empty = isinstance(ops_payload, dict) and not ops_payload
    if ops_status == 0:
        add_missing("operations_unavailable")
    scenarios.append(
        _scenario(
            "operations_unavailable_or_empty",
            "skipped" if ops_status == 0 else ("partial" if ops_empty else "success"),
            missing=["operations_unavailable"] if ops_status == 0 else [],
            evidence={"http_status": ops_status, "payload_empty": ops_empty, "error": ops_error},
        )
    )

    latest_acceptance = _latest_file("docs/reports/acceptance_snapshots/*.json")
    latest_demo = _latest_file("docs/reports/demo_artifacts/**/*.json")
    latest_failure = _latest_file("docs/reports/failure_diagnostics/*.json")
    latest_report_index = _latest_file("docs/reports/report_index/*.json")
    latest_config_drift = _latest_file("docs/reports/config_drift/*.json")
    latest_governance = _latest_file("docs/reports/governance_policy/*.json")
    latest_live_drill = _latest_file("docs/reports/live_drill_window/*.json")

    scenarios.append(_scenario("acceptance_snapshot_online_skipped", "skipped" if not latest_acceptance else "success", missing=[] if latest_acceptance else ["acceptance_snapshot_report_missing"], evidence={"latest_report": latest_acceptance}))
    scenarios.append(_scenario("demo_e2e_online_smoke_skipped", "skipped" if not latest_demo else "success", missing=[] if latest_demo else ["demo_artifact_report_missing"], evidence={"latest_report": latest_demo}))
    scenarios.append(_scenario("failure_diagnostics_blocked_findings", "skipped" if not latest_failure else "success", missing=[] if latest_failure else ["failure_diagnostics_report_missing"], evidence={"latest_report": latest_failure}))
    scenarios.append(_scenario("report_index_empty_or_stale_candidates", "skipped" if not latest_report_index else "success", missing=[] if latest_report_index else ["report_index_missing"], evidence={"latest_report": latest_report_index}))
    scenarios.append(_scenario("config_drift_warnings", "skipped" if not latest_config_drift else "success", missing=[] if latest_config_drift else ["config_drift_report_missing"], evidence={"latest_report": latest_config_drift}))
    scenarios.append(_scenario("governance_or_live_drill_skipped", "skipped" if not (latest_governance and latest_live_drill) else "success", missing=[] if latest_governance and latest_live_drill else ["governance_or_live_drill_report_missing"], evidence={"governance": latest_governance, "live_drill": latest_live_drill}))

    oidc_missing, oidc_evidence = _oidc_missing()
    if oidc_missing:
        for item in oidc_missing:
            add_missing(f"oidc:{item}")
    scenarios.append(_scenario("oidc_secret_env_missing", "skipped" if oidc_missing else "success", missing=oidc_missing, evidence=oidc_evidence))

    llm_missing, llm_evidence = _real_llm_missing()
    if llm_missing:
        for item in llm_missing:
            add_missing(f"real_llm:{item}")
    scenarios.append(_scenario("real_llm_opt_in_missing_or_skipped", "skipped" if llm_missing else "success", missing=llm_missing, evidence=llm_evidence))

    for scenario in scenarios:
        for item in scenario.get("missing_conditions", []):
            add_missing(item)

    return scenarios, missing_conditions


def _derive_status(scenarios: list[dict[str, Any]]) -> str:
    statuses = {item.get("status") for item in scenarios}
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses:
        return "partial"
    if "skipped" in statuses:
        return "skipped"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.4 故障演练包（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- mode: {payload.get('mode', '')}",
        "",
        "## 演练场景",
    ]
    for scenario in payload.get("scenarios", []):
        lines.extend(
            [
                f"### {scenario.get('name', '')}",
                f"- status: {scenario.get('status', '')}",
                f"- missing_conditions: {json.dumps(scenario.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.extend(["## 推荐 runbook"])
    for item in payload.get("recommended_runbooks", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_incident_rehearsal_pack(
    *,
    output_dir: str | Path | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_compose_checks: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    scenarios, missing_conditions = _build_scenarios(base_url=base_url, run_compose_checks=run_compose_checks)
    status = _derive_status(scenarios)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.4.0",
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "scenarios": scenarios,
        "recommended_runbooks": RECOMMENDED_RUNBOOKS,
        "missing_conditions": missing_conditions,
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_incident_rehearsal"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "scenario_count": len(scenarios),
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.4 只读故障演练包（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--run-compose-checks", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_incident_rehearsal_pack(
        output_dir=args.output_dir,
        base_url=args.base_url,
        run_compose_checks=args.run_compose_checks,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
