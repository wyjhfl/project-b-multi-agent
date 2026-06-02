from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.auth.dependencies import ENDPOINT_PERMISSIONS, ROLE_HIERARCHY
from app.auth.models import TokenPayload, User, UserRole
from app.core.config import settings
from app.models.schemas import TenantOwnershipModelDraft

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "identity_tenant_boundary"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
GAP_STATUS_VOCABULARY = ["present", "gap", "planned", "not_applicable"]

BOUNDARY_DECLARATIONS = [
    "只读身份与租户边界盘点",
    "仅读取代码结构、配置键名和安全元数据",
    "不读取 .env 或真实 secret 值",
    "不输出 token、client_secret、JWT_SECRET、DATABASE_URL 或 REDIS_URL 原文",
    "不连接真实外部 IdP",
    "不执行 OIDC token exchange",
    "不改 JWT payload",
    "不新增或启用 tenant enforcement",
    "不默认启用 AUTH_ENABLED、RBAC_ENABLED、OIDC_ENABLED",
    "不写业务数据",
    "不执行真实外网 LLM",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称生产级 SSO/OIDC 已完成",
    "不宣称多租户、复杂 BI 全量完成",
]

TENANT_SCOPE_FIELDS = ["tenant_id", "org_id", "organization_id", "project_id", "resource_scope"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _model_fields(model: type[Any]) -> list[str]:
    return sorted(getattr(model, "model_fields", {}).keys())


def _scope_field_status(fields: list[str]) -> dict[str, bool]:
    field_set = set(fields)
    return {field: field in field_set for field in TENANT_SCOPE_FIELDS}


def _build_identity_model_inventory() -> dict[str, Any]:
    user_fields = _model_fields(User)
    token_fields = _model_fields(TokenPayload)
    return {
        "user_model": {
            "module": "app/auth/models.py",
            "fields": user_fields,
            "roles": [role.value for role in UserRole],
            "tenant_scope_fields": _scope_field_status(user_fields),
            "has_tenant_scope": any(_scope_field_status(user_fields).values()),
        },
        "token_payload": {
            "module": "app/auth/models.py",
            "fields": token_fields,
            "tenant_scope_fields": _scope_field_status(token_fields),
            "has_tenant_scope": any(_scope_field_status(token_fields).values()),
        },
        "jwt": {
            "module": "app/auth/jwt.py",
            "access_token_supported": _path_exists("app/auth/jwt.py"),
            "tenant_scope_in_token": any(_scope_field_status(token_fields).values()),
        },
    }


def _build_rbac_inventory() -> dict[str, Any]:
    return {
        "module": "app/auth/dependencies.py",
        "role_hierarchy": {role: sorted(values) for role, values in sorted(ROLE_HIERARCHY.items())},
        "endpoint_permissions": {
            permission: sorted(roles)
            for permission, roles in sorted(ENDPOINT_PERMISSIONS.items())
        },
        "role_count": len(ROLE_HIERARCHY),
        "permission_count": len(ENDPOINT_PERMISSIONS),
        "default_auth_enabled": bool(settings.auth_enabled),
        "default_rbac_enabled": bool(settings.rbac_enabled),
    }


def _build_oidc_inventory() -> dict[str, Any]:
    oidc_keys = [
        "OIDC_ENABLED",
        "OIDC_ISSUER_URL",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET_ENV",
        "OIDC_REDIRECT_URI",
        "OIDC_SCOPES",
        "OIDC_ROLE_CLAIM",
        "OIDC_DEFAULT_ROLE",
        "OIDC_ALLOWED_ROLES",
        "OIDC_REQUIRE_HTTPS",
    ]
    return {
        "module": "app/auth/oidc_config.py",
        "status_api": "/auth/oidc/status",
        "config_keys": oidc_keys,
        "default_oidc_enabled": bool(settings.oidc_enabled),
        "secret_output_policy": "client_secret_present_bool_only",
        "real_idp_connected": False,
        "token_exchange_supported": False,
        "role_mapping_supported": _path_exists("app/auth/oidc_config.py"),
    }


def _build_audit_inventory() -> dict[str, Any]:
    audit_files = {
        "audit_api": "app/api/audit.py",
        "audit_tests": "tests/test_audit_v045.py",
        "audit_retention_export_tests": "tests/test_audit_retention_export_v74.py",
    }
    scope_fields = {
        "tenant_id": False,
        "org_id": False,
        "project_id": False,
        "resource_scope": False,
    }
    return {
        "files": {
            key: {"path": path, "present": _path_exists(path)}
            for key, path in audit_files.items()
        },
        "tenant_scope_fields": scope_fields,
        "tenant_aware_audit_supported": any(scope_fields.values()),
        "redaction_boundary": "不导出 prompt 原文、密钥原文或连接串密码原文",
    }


def _build_resource_ownership_inventory() -> dict[str, Any]:
    concepts = {
        "organization": True,
        "tenant": True,
        "project": True,
        "principal": True,
        "role_assignment": True,
        "resource_scope": True,
        "audit_scope": True,
    }
    return {
        "concepts": concepts,
        "draft_schema": "app.models.schemas.TenantOwnershipModelDraft",
        "draft_schema_fields": sorted(TenantOwnershipModelDraft.model_fields.keys()),
        "ownership_model_present": True,
        "runtime_enforcement_enabled": False,
        "known_gap": "当前已有 tenant ownership 草案模型，但尚未接入数据库、API、JWT 或运行时 enforcement。",
    }


def _build_gaps(identity: dict[str, Any], audit: dict[str, Any], ownership: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not identity["user_model"]["has_tenant_scope"]:
        gaps.append(
            {
                "gap_id": "identity:user_model_tenant_scope_missing",
                "status": "gap",
                "severity": "high",
                "description": "User 模型缺少 tenant/org/project scope 字段。",
                "recommended_phase": "Phase 16.2",
            }
        )
    if not identity["token_payload"]["has_tenant_scope"]:
        gaps.append(
            {
                "gap_id": "identity:token_payload_tenant_scope_missing",
                "status": "gap",
                "severity": "high",
                "description": "JWT TokenPayload 缺少 tenant/org/project scope 字段。",
                "recommended_phase": "Phase 16.2",
            }
        )
    if not ownership["runtime_enforcement_enabled"]:
        gaps.append(
            {
                "gap_id": "tenant:runtime_enforcement_missing",
                "status": "gap",
                "severity": "high",
                "description": "尚未启用跨租户访问拒绝的运行时 enforcement。",
                "recommended_phase": "Phase 16.5",
            }
        )
    if not audit["tenant_aware_audit_supported"]:
        gaps.append(
            {
                "gap_id": "audit:tenant_scope_missing",
                "status": "gap",
                "severity": "medium",
                "description": "审计事件尚未定义 tenant/org/project scope 字段。",
                "recommended_phase": "Phase 16.5",
            }
        )
    return gaps


def _derive_status(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "success"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.6 身份与租户边界盘点（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- read_only: {payload.get('read_only', True)}",
        f"- real_idp_connected: {payload.get('real_idp_connected', False)}",
        f"- tenant_enforcement_enabled: {payload.get('tenant_enforcement_enabled', False)}",
        "",
        "## 现有能力",
        f"- roles: {json.dumps(payload['identity_model']['user_model']['roles'], ensure_ascii=False)}",
        f"- permission_count: {payload['rbac']['permission_count']}",
        f"- oidc_status_api: {payload['oidc']['status_api']}",
        "",
        "## 缺口",
    ]
    for gap in payload.get("gaps", []):
        lines.append(f"- {gap['gap_id']}：{gap['description']}（{gap['recommended_phase']}）")
    lines.extend(["", "## 建议动作"])
    for action in payload.get("recommended_actions", []):
        lines.append(f"- {action}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_identity_tenant_boundary_inventory(
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    identity = _build_identity_model_inventory()
    rbac = _build_rbac_inventory()
    oidc = _build_oidc_inventory()
    audit = _build_audit_inventory()
    ownership = _build_resource_ownership_inventory()
    gaps = _build_gaps(identity, audit, ownership)
    status = _derive_status(gaps)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.5.0",
        "phase": "v3.6 Phase 16.1",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "gap_status_vocabulary": GAP_STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "real_idp_connected": False,
        "oidc_token_exchange_executed": False,
        "tenant_enforcement_enabled": False,
        "business_data_written": False,
        "default_auth_enabled": bool(settings.auth_enabled),
        "default_rbac_enabled": bool(settings.rbac_enabled),
        "default_oidc_enabled": bool(settings.oidc_enabled),
        "identity_model": identity,
        "rbac": rbac,
        "oidc": oidc,
        "audit": audit,
        "resource_ownership": ownership,
        "gaps": gaps,
        "gap_count": len(gaps),
        "recommended_actions": [
            "优先在 Phase 16.2 定义 tenant/org/project/resource ownership 模型。",
            "在模型落地前，不要把当前 OIDC 配置预检宣称为生产级 SSO/OIDC 完成。",
            "在跨租户拒绝测试和审计隔离测试完成前，不要宣称多租户完成。",
            "保持 AUTH_ENABLED、RBAC_ENABLED、OIDC_ENABLED 默认关闭，保留离线演示路径。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_identity_tenant_boundary_inventory"
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
        "real_idp_connected": False,
        "tenant_enforcement_enabled": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "gap_count": len(gaps),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.6 身份与租户边界只读盘点（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_identity_tenant_boundary_inventory(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
