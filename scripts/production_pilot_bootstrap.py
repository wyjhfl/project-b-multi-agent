from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from fastapi.testclient import TestClient

from app.main import app
from scripts.real_integration_env_profile import build_real_integration_env_profile
from scripts.real_integration_gap_register import build_real_integration_gap_register
from scripts.real_integration_readiness_matrix import build_real_integration_readiness_matrix
from scripts.real_integration_staging_gate import build_real_integration_staging_gate
from scripts.real_integration_staging_smoke import DOMAIN_IDS, build_real_integration_staging_smoke
from scripts.real_production_environment_checklist import build_real_production_environment_checklist
from scripts.production_migration_drill import build_production_migration_drill
from scripts.business_system_integration_safety_checklist import build_business_system_integration_safety_checklist
from scripts.production_auth_rbac_acceptance import build_production_auth_rbac_acceptance
from scripts.business_system_read_smoke import build_business_system_read_smoke
from scripts.frontend_production_build_check import build_frontend_production_build_check
from scripts.production_runtime_smoke import build_production_runtime_smoke
from scripts.operations_console_landing_smoke import build_operations_console_landing_smoke
from scripts.production_landing_final_verification import build_production_landing_final_verification
from scripts.production_pilot_evidence_bundle import build_production_pilot_evidence_bundle

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_pilot_bootstrap"
DEFAULT_STAGING_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke"
SIGNOFF_CLOSEOUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _local_service_smoke() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for path in ["/health", "/operations/summary"]:
            try:
                response = client.get(path)
                checks.append(
                    {
                        "path": path,
                        "status": "success" if response.status_code == 200 else "failed",
                        "http_status": response.status_code,
                    }
                )
            except Exception as exc:
                checks.append(
                    {
                        "path": path,
                        "status": "failed",
                        "http_status": None,
                        "error_type": exc.__class__.__name__,
                    }
                )
    status = "success" if checks and all(item["status"] == "success" for item in checks) else "failed"
    return {"status": status, "checks": checks, "check_count": len(checks)}


def _derive_status(local_smoke: dict[str, Any], evidence: list[dict[str, Any]], execute_real_smoke: bool) -> str:
    if local_smoke.get("status") == "failed":
        return "failed"
    if execute_real_smoke:
        staging_smoke = next(
            (item for item in evidence if item.get("evidence_id") == "real_integration_staging_smoke"),
            None,
        )
        staging_status = str((staging_smoke or {}).get("status") or "skipped")
        if staging_status == "success":
            return "partial"
        if staging_status == "failed":
            return "failed"
        return "blocked"
    evidence_statuses = [str(item.get("status") or "skipped") for item in evidence]
    if any(item.get("secret_plaintext_output") is True or item.get("business_data_written") is True for item in evidence):
        return "blocked"
    pilot_bundle = next((item for item in evidence if item.get("evidence_id") == "production_pilot_evidence_bundle"), None)
    if pilot_bundle and pilot_bundle.get("status") == "success":
        return "partial"
    if any(status in {"skipped", "blocked"} for status in evidence_statuses):
        return "skipped"
    return "partial"


def _latest_successful_real_llm_evidence(report_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(report_dir) if report_dir else DEFAULT_STAGING_SMOKE_DIR
    if not root.exists() or not root.is_dir():
        return {
            "evidence_id": "real_llm_historical_staging_smoke",
            "status": "skipped",
            "latest_report_present": False,
            "real_llm_executed": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["real_llm_success_report:not_found"],
        }

    candidates: list[tuple[str, float, Path, dict[str, Any]]] = []
    for item in root.glob("*.json"):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "success" and payload.get("real_llm_executed") is True:
            candidates.append((str(payload.get("generated_at") or ""), item.stat().st_mtime, item, payload))
    if not candidates:
        return {
            "evidence_id": "real_llm_historical_staging_smoke",
            "status": "skipped",
            "latest_report_present": False,
            "real_llm_executed": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["real_llm_success_report:not_found"],
        }

    _, _, path, payload = max(candidates, key=lambda item: (item[0], item[1], item[2].name))
    return {
        "evidence_id": "real_llm_historical_staging_smoke",
        "status": "success",
        "latest_report_present": True,
        "latest_json_path": str(path),
        "generated_at": payload.get("generated_at"),
        "real_llm_executed": True,
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "network_check_evidence_present": any(
            domain.get("domain_id") == "real_llm"
            and domain.get("evidence", {}).get("network_check_executed") is True
            for domain in payload.get("domains", [])
            if isinstance(domain, dict)
        ),
        "missing_conditions": [],
    }


def _latest_report_evidence(evidence_id: str, report_dir: str | Path, pattern: str) -> dict[str, Any]:
    root = Path(report_dir)
    if not root.exists() or not root.is_dir():
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "latest_report_present": False,
            "secret_plaintext_output": False,
            "missing_conditions": [f"{evidence_id}:report_not_found"],
        }
    files = [item for item in root.glob(pattern) if item.is_file()]
    if not files:
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "latest_report_present": False,
            "secret_plaintext_output": False,
            "missing_conditions": [f"{evidence_id}:report_not_found"],
        }

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return generated_at, item.stat().st_mtime, item.name

    path = max(files, key=sort_key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "evidence_id": evidence_id,
            "status": "blocked",
            "latest_report_present": True,
            "latest_json_path": str(path),
            "secret_plaintext_output": False,
            "missing_conditions": [f"{evidence_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        payload = {}
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "evidence_id": evidence_id,
        "status": str(payload.get("status") or "skipped"),
        "latest_report_present": True,
        "latest_json_path": str(path),
        "generated_at": payload.get("generated_at"),
        "final_status": payload.get("final_status"),
        "controlled_pilot_ready": payload.get("controlled_pilot_ready"),
        "missing_condition_count": payload.get("missing_condition_count"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": payload.get("public_production_direct_launch")
        or (payload.get("go_no_go") or {}).get("public_production_direct_launch")
        or "No-Go",
        "missing_conditions": [str(item) for item in missing[:12]],
    }


def _build_operations_console_smoke_evidence(*, execute: bool) -> dict[str, Any]:
    try:
        return build_operations_console_landing_smoke(execute=execute)
    except TypeError:
        return build_operations_console_landing_smoke()


def _next_commands() -> dict[str, list[str]]:
    return {
        "local_pilot": [
            "python scripts/production_pilot_bootstrap.py",
            "python scripts/real_production_environment_checklist.py",
            "python -m pytest tests/test_real_production_environment_checklist_v45.py tests/test_real_integration_staging_smoke_v446.py -q",
        ],
        "real_llm": [
            "设置 REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "设置 REAL_LLM_STAGING_SMOKE_EXECUTE=true",
            "设置 REAL_LLM_ACCEPTANCE_ENABLED=true、REAL_LLM_PREFLIGHT_ENABLED=true、REAL_LLM_SMOKE_ENABLED=true、REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
            "设置 REAL_LLM_PROVIDER、REAL_LLM_MODEL、REAL_LLM_API_KEY_ENV，并在外部环境中提供该变量指向的密钥",
            "python scripts/production_pilot_bootstrap.py --execute-real-smoke --domains real_llm",
        ],
        "postgres": [
            "设置 STORAGE_BACKEND=postgres",
            "通过外部 secret 注入 DATABASE_URL",
            "确认 Alembic migration 执行窗口和回滚点",
            "python scripts/production_pilot_bootstrap.py --execute-real-smoke --domains postgres",
        ],
        "redis": [
            "设置 REDIS_ENABLED=true",
            "通过外部 secret 注入 REDIS_URL",
            "设置 RATE_LIMIT_BACKEND=redis",
            "python scripts/production_pilot_bootstrap.py --execute-real-smoke --domains redis",
        ],
        "external_mcp": [
            "设置 MCP_MODE=real",
            "设置 MCP_SERVER_COMMAND、MCP_SERVER_COMMAND_ALLOWLIST、MCP_TOOL_ALLOWLIST",
            "按需设置 MCP_SERVER_ENV_ALLOWLIST、MCP_SERVER_TIMEOUT_SECONDS",
            "python scripts/production_pilot_bootstrap.py --execute-real-smoke --domains external_mcp",
        ],
        "frontend": [
            "确认 frontend/node_modules 已安装",
            "python scripts/frontend_production_build_check.py --execute",
            "python scripts/production_pilot_bootstrap.py --execute-frontend-build-check",
        ],
        "runtime_smoke": [
            "python scripts/production_runtime_smoke.py",
            "复核 /health、/deployment/check、/operations/summary 的结构化 smoke 报告",
            "python scripts/production_pilot_bootstrap.py --include-runtime-smoke",
        ],
        "final_closeout": [
            "python scripts/production_landing_final_verification.py",
            "python scripts/production_pilot_evidence_bundle.py",
            "python scripts/production_pilot_bootstrap.py",
        ],
    }


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    commit = str(payload.get("commit") or "unknown")
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_production_pilot_bootstrap"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产试点启动总入口报告",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute_real_smoke: {payload.get('execute_real_smoke', False)}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        "",
        "## 本地服务校验",
    ]
    local_smoke = payload.get("local_service_smoke", {})
    lines.append(f"- status: {local_smoke.get('status', '')}")
    for item in local_smoke.get("checks", []):
        lines.append(f"- {item.get('path')}: {item.get('status')} ({item.get('http_status')})")

    lines.extend(["", "## 证据生成"])
    for item in payload.get("evidence_runs", []):
        lines.append(f"- {item.get('evidence_id')}: {item.get('status')} -> `{item.get('json_path')}`")

    lines.extend(["", "## 下一步命令"])
    for group, commands in payload.get("next_commands", {}).items():
        lines.append(f"### {group}")
        for command in commands:
            lines.append(f"- `{command}`" if command.startswith("python ") else f"- {command}")
    lines.append("")
    return "\n".join(lines)


def build_production_pilot_bootstrap(
    *,
    output_dir: str | Path | None = None,
    execute_real_smoke: bool = False,
    execute_migration_drill: bool = False,
    execute_auth_rbac_acceptance: bool = False,
    execute_business_read_smoke: bool = False,
    execute_frontend_build_check: bool = False,
    execute_operations_console_smoke: bool = False,
    include_runtime_smoke: bool = False,
    domains: list[str] | None = None,
    historical_llm_report_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    selected_domains = domains or DOMAIN_IDS

    local_smoke = _local_service_smoke()
    runtime_smoke = (
        build_production_runtime_smoke()
        if include_runtime_smoke
        else {
            "status": "skipped",
            "mode": "in_process_runtime_smoke",
            "endpoint_check_count": 0,
            "operations_contract_status": "skipped",
            "frontend_build_status": "skipped",
            "frontend_build_executed": False,
            "bootstrap_status": "skipped",
            "business_system_connected": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["runtime_smoke:include_runtime_smoke_not_requested"],
        }
    )
    evidence_runs = [
        {"evidence_id": "real_integration_readiness", **build_real_integration_readiness_matrix()},
        {"evidence_id": "real_integration_env_profile", **build_real_integration_env_profile()},
        _latest_successful_real_llm_evidence(historical_llm_report_dir),
        {
            "evidence_id": "real_integration_staging_smoke",
            **build_real_integration_staging_smoke(execute=execute_real_smoke, domains=selected_domains),
        },
        {
            "evidence_id": "production_migration_drill",
            **build_production_migration_drill(execute=execute_migration_drill),
        },
        {
            "evidence_id": "business_system_integration_safety",
            **build_business_system_integration_safety_checklist(),
        },
        {
            "evidence_id": "business_system_read_smoke",
            **build_business_system_read_smoke(execute=execute_business_read_smoke),
        },
        {
            "evidence_id": "production_auth_rbac_acceptance",
            **build_production_auth_rbac_acceptance(execute=execute_auth_rbac_acceptance),
        },
        {
            "evidence_id": "frontend_production_build",
            **build_frontend_production_build_check(execute=execute_frontend_build_check),
        },
        {
            "evidence_id": "production_runtime_smoke",
            **runtime_smoke,
        },
        _latest_report_evidence(
            "production_landing_signoff_closeout",
            SIGNOFF_CLOSEOUT_DIR,
            "*_production_landing_signoff_closeout.json",
        ),
        {
            "evidence_id": "operations_console_landing_smoke",
            **_build_operations_console_smoke_evidence(execute=execute_operations_console_smoke),
        },
        {
            "evidence_id": "production_landing_final_verification",
            **build_production_landing_final_verification(),
        },
        {
            "evidence_id": "production_pilot_evidence_bundle",
            **build_production_pilot_evidence_bundle(),
        },
        {"evidence_id": "real_integration_staging_gate", **build_real_integration_staging_gate()},
        {"evidence_id": "real_integration_gap_register", **build_real_integration_gap_register()},
        {"evidence_id": "real_production_environment_checklist", **build_real_production_environment_checklist()},
    ]
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    status = _derive_status(local_smoke, evidence_runs, execute_real_smoke)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.10",
        "phase": "v4.8 Production Pilot Bootstrap",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "execute_real_smoke": execute_real_smoke,
        "execute_migration_drill": execute_migration_drill,
        "execute_auth_rbac_acceptance": execute_auth_rbac_acceptance,
        "execute_business_read_smoke": execute_business_read_smoke,
        "execute_frontend_build_check": execute_frontend_build_check,
        "execute_operations_console_smoke": execute_operations_console_smoke,
        "include_runtime_smoke": include_runtime_smoke,
        "requested_domains": selected_domains,
        "local_service_smoke": local_smoke,
        "evidence_runs": evidence_runs,
        "evidence_count": len(evidence_runs),
        "next_commands": _next_commands(),
        "real_llm_executed": any(item.get("real_llm_executed") is True for item in evidence_runs),
        "database_connected": any(item.get("database_connected") is True for item in evidence_runs),
        "redis_connected": any(item.get("redis_connected") is True for item in evidence_runs),
        "external_mcp_connected": any(item.get("external_mcp_connected") is True for item in evidence_runs),
        "migration_executed": any(item.get("migration_executed") is True for item in evidence_runs),
        "business_system_connected": any(item.get("business_system_connected") is True for item in evidence_runs),
        "business_read_executed": any(item.get("business_read_executed") is True for item in evidence_runs),
        "business_write_executed": any(item.get("business_write_executed") is True for item in evidence_runs),
        "business_data_written": any(item.get("business_data_written") is True for item in evidence_runs),
        "auth_rbac_acceptance_passed": any(
            item.get("evidence_id") == "production_auth_rbac_acceptance" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "frontend_build_passed": any(
            item.get("evidence_id") == "frontend_production_build" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "frontend_build_executed": any(item.get("build_executed") is True for item in evidence_runs),
        "frontend_build_return_code": next(
            (
                item.get("return_code")
                for item in evidence_runs
                if item.get("evidence_id") == "frontend_production_build"
            ),
            None,
        ),
        "runtime_smoke_passed": any(
            item.get("evidence_id") == "production_runtime_smoke" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "runtime_smoke_endpoint_check_count": next(
            (
                item.get("endpoint_check_count")
                for item in evidence_runs
                if item.get("evidence_id") == "production_runtime_smoke"
            ),
            0,
        ),
        "signoff_closeout_passed": any(
            item.get("evidence_id") == "production_landing_signoff_closeout" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "final_verification_passed": any(
            item.get("evidence_id") == "production_landing_final_verification" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "pilot_evidence_bundle_passed": any(
            item.get("evidence_id") == "production_pilot_evidence_bundle" and item.get("status") == "success"
            for item in evidence_runs
        ),
        "operations_console_smoke_status": next(
            (
                item.get("status")
                for item in evidence_runs
                if item.get("evidence_id") == "operations_console_landing_smoke"
            ),
            "skipped",
        ),
        "auth_enabled": any(item.get("auth_enabled") is True for item in evidence_runs),
        "rbac_enabled": any(item.get("rbac_enabled") is True for item in evidence_runs),
        "jwt_token_issued": any(item.get("jwt_token_issued") is True for item in evidence_runs),
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "production_pilot": "Manual-Review" if status == "partial" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": str(output_root),
    }
    paths = _write_report(payload, output_root)
    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "execute_real_smoke": execute_real_smoke,
        "execute_migration_drill": execute_migration_drill,
        "execute_auth_rbac_acceptance": execute_auth_rbac_acceptance,
        "execute_business_read_smoke": execute_business_read_smoke,
        "execute_frontend_build_check": execute_frontend_build_check,
        "execute_operations_console_smoke": execute_operations_console_smoke,
        "include_runtime_smoke": include_runtime_smoke,
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "output_dir": str(output_root),
        "local_service_status": local_smoke.get("status"),
        "evidence_count": len(evidence_runs),
        "real_llm_executed": payload["real_llm_executed"],
        "database_connected": payload["database_connected"],
        "redis_connected": payload["redis_connected"],
        "external_mcp_connected": payload["external_mcp_connected"],
        "migration_executed": payload["migration_executed"],
        "business_system_connected": payload["business_system_connected"],
        "business_read_executed": payload["business_read_executed"],
        "business_write_executed": payload["business_write_executed"],
        "business_data_written": payload["business_data_written"],
        "auth_rbac_acceptance_passed": payload["auth_rbac_acceptance_passed"],
        "frontend_build_passed": payload["frontend_build_passed"],
        "frontend_build_executed": payload["frontend_build_executed"],
        "frontend_build_return_code": payload["frontend_build_return_code"],
        "runtime_smoke_passed": payload["runtime_smoke_passed"],
        "runtime_smoke_endpoint_check_count": payload["runtime_smoke_endpoint_check_count"],
        "signoff_closeout_passed": payload["signoff_closeout_passed"],
        "final_verification_passed": payload["final_verification_passed"],
        "pilot_evidence_bundle_passed": payload["pilot_evidence_bundle_passed"],
        "operations_console_smoke_status": payload["operations_console_smoke_status"],
        "auth_enabled": payload["auth_enabled"],
        "rbac_enabled": payload["rbac_enabled"],
        "jwt_token_issued": payload["jwt_token_issued"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行生产试点启动总入口，默认只做离线本地校验和只读证据生成。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute-real-smoke", action="store_true", help="请求执行真实 staging smoke；仍受环境 opt-in 拦截。")
    parser.add_argument("--execute-migration-drill", action="store_true", help="请求执行受控 Alembic migration 演练；仍受环境 opt-in 拦截。")
    parser.add_argument("--execute-auth-rbac-acceptance", action="store_true", help="执行进程内生产 Auth/RBAC 受控验收。")
    parser.add_argument("--execute-business-read-smoke", action="store_true", help="执行受控业务系统只读 smoke；仍受环境 opt-in 拦截。")
    parser.add_argument("--execute-frontend-build-check", action="store_true", help="执行前端生产构建检查。")
    parser.add_argument("--execute-operations-console-smoke", action="store_true", help="执行本地运营台页面与 summary smoke。")
    parser.add_argument("--include-runtime-smoke", action="store_true", help="纳入进程内生产运行 smoke。")
    parser.add_argument("--domains", default=",".join(DOMAIN_IDS), help="逗号分隔的真实 smoke 域。")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    domains = [item.strip() for item in str(args.domains or "").split(",") if item.strip()]
    summary = build_production_pilot_bootstrap(
        output_dir=args.output_dir,
        execute_real_smoke=args.execute_real_smoke,
        execute_migration_drill=args.execute_migration_drill,
        execute_auth_rbac_acceptance=args.execute_auth_rbac_acceptance,
        execute_business_read_smoke=args.execute_business_read_smoke,
        execute_frontend_build_check=args.execute_frontend_build_check,
        execute_operations_console_smoke=args.execute_operations_console_smoke,
        include_runtime_smoke=args.include_runtime_smoke,
        domains=domains,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
