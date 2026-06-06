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

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_runtime_smoke"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_MARKERS = (
    "sk-",
    "tp-",
    "bearer ",
    "api_key=",
    "apikey=",
    "token=",
    "password=",
    "client_secret=",
    "jwt_secret=",
    "postgresql://",
    "postgres://",
    "redis://",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    lowered = text.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return "[redacted-secret-like-text]" if _contains_secret_like(text) else text


def _collect_endpoint_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for path in ("/health", "/operations/summary", "/deployment/check"):
            try:
                response = client.get(path)
                checks.append(
                    {
                        "path": path,
                        "http_status": response.status_code,
                        "passed": response.status_code == 200,
                        "response_json_present": response.headers.get("content-type", "").startswith("application/json"),
                    }
                )
            except Exception as exc:
                checks.append(
                    {
                        "path": path,
                        "http_status": None,
                        "passed": False,
                        "response_json_present": False,
                        "error_type": exc.__class__.__name__,
                    }
                )
    return checks


def _collect_operations_contract() -> dict[str, Any]:
    with TestClient(app) as client:
        response = client.get("/operations/summary")
    if response.status_code != 200:
        return {
            "status": "failed",
            "http_status": response.status_code,
            "missing_conditions": ["operations_summary:http_status_not_200"],
        }

    try:
        payload = response.json()
    except Exception as exc:
        return {
            "status": "failed",
            "http_status": response.status_code,
            "missing_conditions": [f"operations_summary:json_parse_failed:{exc.__class__.__name__}"],
        }

    observability = payload.get("observability") if isinstance(payload.get("observability"), dict) else {}
    frontend_build = observability.get("frontend_production_build")
    bootstrap = observability.get("production_pilot_bootstrap")
    deployment = payload.get("deployment") if isinstance(payload.get("deployment"), dict) else {}
    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}

    missing_conditions: list[str] = []
    if not isinstance(frontend_build, dict):
        missing_conditions.append("operations_summary:frontend_production_build_missing")
        frontend_build = {}
    if not isinstance(bootstrap, dict):
        missing_conditions.append("operations_summary:production_pilot_bootstrap_missing")
        bootstrap = {}
    if str(health.get("status") or "") != "ok":
        missing_conditions.append("operations_summary:health_status_not_ok")
    if str((frontend_build or {}).get("public_production_direct_launch") or "No-Go") != "No-Go":
        missing_conditions.append("operations_summary:frontend_public_launch_not_no_go")
    if str((bootstrap or {}).get("public_production_direct_launch") or "No-Go") != "No-Go":
        missing_conditions.append("operations_summary:bootstrap_public_launch_not_no_go")
    if bool((frontend_build or {}).get("secret_plaintext_output", False)):
        missing_conditions.append("operations_summary:frontend_secret_plaintext_output")
    if bool((bootstrap or {}).get("secret_plaintext_output", False)):
        missing_conditions.append("operations_summary:bootstrap_secret_plaintext_output")

    return {
        "status": "success" if not missing_conditions else "blocked",
        "http_status": response.status_code,
        "missing_conditions": missing_conditions,
        "health_status": str(health.get("status") or ""),
        "deployment_ok": bool(deployment.get("ok", False)),
        "deployment_error_count": int(deployment.get("error_count", 0) or 0),
        "frontend_build_status": str((frontend_build or {}).get("status") or "skipped"),
        "frontend_build_executed": bool((frontend_build or {}).get("build_executed", False)),
        "frontend_build_return_code": (frontend_build or {}).get("return_code"),
        "bootstrap_status": str((bootstrap or {}).get("status") or "skipped"),
        "bootstrap_evidence_count": int((bootstrap or {}).get("evidence_count", 0) or 0),
        "auth_rbac_acceptance_passed": bool((bootstrap or {}).get("auth_rbac_acceptance_passed", False)),
        "business_system_connected": bool((bootstrap or {}).get("business_system_connected", False)),
        "public_production_direct_launch": "No-Go",
    }


def _derive_status(endpoint_checks: list[dict[str, Any]], operations_contract: dict[str, Any]) -> str:
    if _contains_secret_like(endpoint_checks) or _contains_secret_like(operations_contract):
        return "blocked"
    if not endpoint_checks or any(item.get("passed") is not True for item in endpoint_checks):
        return "failed"
    if operations_contract.get("status") == "blocked":
        return "blocked"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产运行 Smoke 报告",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 端点检查",
    ]
    for item in payload.get("endpoint_checks", []):
        lines.append(
            f"- {item.get('path')}: passed={item.get('passed')} http_status={item.get('http_status')}"
        )
    contract = payload.get("operations_contract", {})
    lines.extend(
        [
            "",
            "## 运营总览契约",
            f"- health_status: {contract.get('health_status', '')}",
            f"- frontend_build_status: {contract.get('frontend_build_status', '')}",
            f"- frontend_build_executed: {contract.get('frontend_build_executed', False)}",
            f"- bootstrap_status: {contract.get('bootstrap_status', '')}",
            f"- bootstrap_evidence_count: {contract.get('bootstrap_evidence_count', 0)}",
            f"- business_system_connected: {contract.get('business_system_connected', False)}",
            "",
            "## 边界",
            "- 进程内 TestClient smoke，不启动外部服务。",
            "- 不执行真实 LLM，不连接真实业务系统，不写业务数据。",
            "- public_production_direct_launch 固定为 No-Go，仍需人工 Go/No-Go。",
            "",
        ]
    )
    return "\n".join(lines)


def build_production_runtime_smoke(
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    if _contains_secret_like(commit):
        commit = "redacted"

    endpoint_checks = _collect_endpoint_checks()
    operations_contract = _collect_operations_contract()
    status = _derive_status(endpoint_checks, operations_contract)
    secret_plaintext_output = False

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.5",
        "phase": "v4.5 Phase 25.7 Production Runtime Smoke",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "mode": "in_process_runtime_smoke",
        "endpoint_checks": endpoint_checks,
        "operations_contract": operations_contract,
        "real_llm_executed": False,
        "business_system_connected": bool(operations_contract.get("business_system_connected", False)),
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": secret_plaintext_output,
        "go_no_go": {
            "production_runtime_smoke": "Manual-Review" if status == "success" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": _safe_text(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["go_no_go"]["production_runtime_smoke"] = "Needs-Input"

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_runtime_smoke"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "endpoint_check_count": len(endpoint_checks),
        "operations_contract_status": operations_contract.get("status"),
        "frontend_build_status": operations_contract.get("frontend_build_status"),
        "frontend_build_executed": operations_contract.get("frontend_build_executed"),
        "bootstrap_status": operations_contract.get("bootstrap_status"),
        "business_system_connected": payload["business_system_connected"],
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产运行 smoke 报告。默认只做进程内只读检查。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_runtime_smoke(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
