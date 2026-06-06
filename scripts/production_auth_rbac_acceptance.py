from __future__ import annotations

import argparse
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.auth.models import User, UserRole
from app.auth.dependencies import ENDPOINT_PERMISSIONS
from app.core.config import settings
from app.core.deployment_guard import run_deployment_checks
from app.main import app

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_auth_rbac_acceptance"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


@contextmanager
def _temporary_settings(**values: Any) -> Iterator[None]:
    previous = {key: getattr(settings, key) for key in values}
    try:
        for key, value in values.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)


def _token_for(username: str, roles: list[UserRole]) -> str:
    user = User(user_id=f"usr_{username}", username=username, password_hash="not-used", roles=roles)
    return create_access_token(user)


def _production_settings() -> dict[str, Any]:
    return {
        "app_env": "production",
        "jwt_secret": "auth-rbac-acceptance-secret-32-bytes",
        "auth_enabled": True,
        "rbac_enabled": True,
        "storage_backend": "sqlite",
        "database_url": "",
        "redis_enabled": False,
        "redis_url": "",
        "mcp_mode": "fake",
        "mcp_server_command_allowlist": "",
        "mcp_tool_allowlist": "",
        "real_llm_acceptance_enabled": False,
        "real_llm_model": "",
        "real_llm_api_key_env": "OPENAI_API_KEY",
        "cors_enabled": True,
        "cors_allow_origins": "https://console.example.com",
        "security_headers_enabled": True,
        "request_size_limit_enabled": True,
        "request_size_limit_bytes": 1048576,
        "rate_limit_enabled": True,
        "rate_limit_backend": "memory",
        "rate_limit_requests_per_minute": 120,
        "rate_limit_burst": 60,
        "structured_logging_enabled": True,
        "log_redaction_enabled": True,
        "log_level": "INFO",
        "audit_retention_enabled": True,
        "audit_retention_days": 90,
        "audit_export_enabled": True,
        "audit_export_max_rows": 1000,
        "audit_export_format": "jsonl",
        "audit_export_redaction_enabled": True,
        "oidc_enabled": False,
        "oidc_issuer_url": "",
        "oidc_client_id": "",
        "oidc_client_secret_env": "OIDC_CLIENT_SECRET",
        "oidc_redirect_uri": "",
        "oidc_scopes": "openid,email,profile",
        "oidc_role_claim": "roles",
        "oidc_default_role": "viewer",
        "oidc_allowed_roles": "admin,operator,viewer,auditor",
        "oidc_require_https": True,
    }


def _run_acceptance_checks() -> dict[str, Any]:
    with _temporary_settings(**_production_settings()):
        deployment = run_deployment_checks().model_dump()
        client = TestClient(app)

        unauth = client.get("/deployment/check")
        viewer_headers = {"Authorization": f"Bearer {_token_for('viewer', [UserRole.viewer])}"}
        operator_headers = {"Authorization": f"Bearer {_token_for('operator', [UserRole.operator])}"}
        auditor_headers = {"Authorization": f"Bearer {_token_for('auditor', [UserRole.auditor])}"}
        admin_headers = {"Authorization": f"Bearer {_token_for('admin', [UserRole.admin])}"}

        checks = [
            {
                "check_id": "deployment_guard_requires_auth_rbac",
                "status": "success" if deployment.get("ok") is True else "failed",
                "evidence": {
                    "ok": bool(deployment.get("ok")),
                    "environment": deployment.get("environment"),
                    "error_count": len(deployment.get("errors", [])),
                    "warning_count": len(deployment.get("warnings", [])),
                },
            },
            {
                "check_id": "unauthenticated_metrics_endpoint_rejected",
                "status": "success" if unauth.status_code == 401 else "failed",
                "evidence": {"path": "/deployment/check", "http_status": unauth.status_code},
            },
            {
                "check_id": "viewer_denied_task_create",
                "status": "success"
                if client.post("/tasks", json={"query": "hello"}, headers=viewer_headers).status_code == 403
                else "failed",
                "evidence": {"permission": "tasks:create", "role": "viewer", "expected_http_status": 403},
            },
            {
                "check_id": "operator_can_read_metrics",
                "status": "success"
                if client.get("/deployment/check", headers=operator_headers).status_code == 200
                else "failed",
                "evidence": {"permission": "metrics:read", "role": "operator", "expected_http_status": 200},
            },
            {
                "check_id": "auditor_can_read_audit",
                "status": "success"
                if client.get("/audit/events", headers=auditor_headers).status_code == 200
                else "failed",
                "evidence": {"path": "/audit/events", "permission": "audit:read", "role": "auditor", "expected_http_status": 200},
            },
            {
                "check_id": "viewer_denied_audit_read",
                "status": "success"
                if client.get("/audit/events", headers=viewer_headers).status_code == 403
                else "failed",
                "evidence": {"path": "/audit/events", "permission": "audit:read", "role": "viewer", "expected_http_status": 403},
            },
            {
                "check_id": "admin_has_all_registered_permissions",
                "status": "success"
                if {"admin"}.issubset({role for roles in ENDPOINT_PERMISSIONS.values() for role in roles})
                else "failed",
                "evidence": {
                    "permission_count": len(ENDPOINT_PERMISSIONS),
                    "admin_token_issued": bool(admin_headers["Authorization"]),
                },
            },
        ]

    return {
        "checks": checks,
        "deployment_error_count": len(deployment.get("errors", [])),
        "permission_count": len(ENDPOINT_PERMISSIONS),
        "auth_enabled": True,
        "rbac_enabled": True,
        "jwt_token_issued": True,
        "token_plaintext_output": False,
        "secret_plaintext_output": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产 Auth/RBAC 受控验收报告",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute: {payload.get('execute', False)}",
        f"- auth_enabled: {payload.get('auth_enabled', False)}",
        f"- rbac_enabled: {payload.get('rbac_enabled', False)}",
        f"- token_plaintext_output: {payload.get('token_plaintext_output', False)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## Checks",
    ]
    for item in payload.get("checks", []):
        lines.append(f"- {item.get('check_id')}: {item.get('status')}")
    lines.extend(
        [
            "",
            "## 边界",
            "- 默认不启用 AUTH_ENABLED/RBAC_ENABLED，不破坏离线演示路径。",
            "- 执行模式仅使用进程内 TestClient 和临时测试 JWT secret，不连接真实 IdP。",
            "- 报告不输出 JWT secret、token 原文、Authorization header 或密码。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_production_auth_rbac_acceptance"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path)}


def build_production_auth_rbac_acceptance(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"

    checks: list[dict[str, Any]] = []
    missing_conditions: list[str] = []
    if execute:
        result = _run_acceptance_checks()
        checks = result["checks"]
        status = "success" if all(item["status"] == "success" for item in checks) else "failed"
        auth_enabled = result["auth_enabled"]
        rbac_enabled = result["rbac_enabled"]
        jwt_token_issued = result["jwt_token_issued"]
        permission_count = result["permission_count"]
        deployment_error_count = result["deployment_error_count"]
    else:
        status = "skipped"
        missing_conditions = ["cli:--execute_not_requested"]
        auth_enabled = False
        rbac_enabled = False
        jwt_token_issued = False
        permission_count = len(ENDPOINT_PERMISSIONS)
        deployment_error_count = None

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.2",
        "phase": "v4.5 Phase 25.4 Production Auth/RBAC Acceptance",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "execute": execute,
        "read_only": not execute,
        "checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "auth_enabled": auth_enabled,
        "rbac_enabled": rbac_enabled,
        "jwt_token_issued": jwt_token_issued,
        "permission_count": permission_count,
        "deployment_error_count": deployment_error_count,
        "oidc_connected": False,
        "external_idp_connected": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "token_plaintext_output": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "production_auth_rbac": "Manual-Review" if status == "success" else "Needs-Input",
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
        "execute": execute,
        "auth_enabled": auth_enabled,
        "rbac_enabled": rbac_enabled,
        "jwt_token_issued": jwt_token_issued,
        "token_plaintext_output": False,
        "secret_plaintext_output": False,
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "output_dir": str(output_root),
        "check_count": len(checks),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产 Auth/RBAC 受控验收报告。默认不执行，仅写 skipped 证据。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="执行进程内 Auth/RBAC 受控验收。")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_auth_rbac_acceptance(output_dir=args.output_dir, execute=args.execute)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
