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
from app.core.config import settings

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "rbac_permission_matrix"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
ROLES = ["admin", "operator", "viewer", "auditor"]

PERMISSION_ACTIONS: dict[str, dict[str, str]] = {
    "tasks:create": {"resource": "tasks", "action": "create", "risk": "write"},
    "tasks:read": {"resource": "tasks", "action": "read", "risk": "read"},
    "approvals:decide": {"resource": "approvals", "action": "decide", "risk": "write"},
    "approvals:read": {"resource": "approvals", "action": "read", "risk": "read"},
    "audit:read": {"resource": "audit", "action": "read", "risk": "sensitive_read"},
    "audit:export": {"resource": "audit", "action": "export", "risk": "sensitive_read"},
    "metrics:read": {"resource": "metrics", "action": "read", "risk": "read"},
    "tools:call": {"resource": "tools", "action": "call", "risk": "write"},
    "tools:read": {"resource": "tools", "action": "read", "risk": "read"},
    "eval:run": {"resource": "eval", "action": "run", "risk": "write"},
    "eval:read": {"resource": "eval", "action": "read", "risk": "read"},
    "memory:manage": {"resource": "memory", "action": "manage", "risk": "write"},
    "reflection:run": {"resource": "reflection", "action": "run", "risk": "write"},
    "snapshot:manage": {"resource": "snapshot", "action": "manage", "risk": "admin"},
}

BOUNDARY_DECLARATIONS = [
    "只读 RBAC 权限矩阵导出",
    "仅读取 ROLE_HIERARCHY 与 ENDPOINT_PERMISSIONS",
    "不新增生产登录系统",
    "不绕过 require_permission",
    "不改变默认 API token 要求",
    "不默认启用 AUTH_ENABLED 或 RBAC_ENABLED",
    "不写业务数据",
    "不读取或输出真实 secret 原文",
    "不执行真实外网 LLM",
    "不连接真实外部 IdP",
    "不宣称权限治理已生产完成",
    "不宣称生产级 SSO/OIDC 或多租户完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _expanded_roles(role: str) -> set[str]:
    return set(ROLE_HIERARCHY.get(role, {role}))


def _role_allowed(role: str, allowed_roles: set[str]) -> bool:
    return bool(_expanded_roles(role) & allowed_roles)


def _matrix_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for permission, allowed_roles in sorted(ENDPOINT_PERMISSIONS.items()):
        allowed = set(allowed_roles)
        role_matrix = {
            role: {
                "allowed": _role_allowed(role, allowed),
                "expanded_roles": sorted(_expanded_roles(role)),
            }
            for role in ROLES
        }
        denied_roles = [role for role in ROLES if not role_matrix[role]["allowed"]]
        metadata = PERMISSION_ACTIONS.get(permission, {"resource": "unknown", "action": "unknown", "risk": "unknown"})
        rows.append(
            {
                "permission": permission,
                "resource": metadata["resource"],
                "action": metadata["action"],
                "risk": metadata["risk"],
                "allowed_roles": sorted(allowed),
                "denied_roles": denied_roles,
                "role_matrix": role_matrix,
                "least_privilege_note": _least_privilege_note(permission, denied_roles),
                "rejection_evidence": {
                    "missing_or_invalid_token": 401,
                    "authenticated_but_not_authorized": 403,
                },
            }
        )
    return rows


def _least_privilege_note(permission: str, denied_roles: list[str]) -> str:
    if not denied_roles:
        return "所有当前角色均可访问；后续 tenant scope enforcement 前需重新复核。"
    return f"{permission} 拒绝角色：{', '.join(denied_roles)}。"


def _derive_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "skipped"
    if any(row["permission"] not in PERMISSION_ACTIONS for row in rows):
        return "partial"
    return "success"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.6 RBAC 权限矩阵（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- read_only: {payload.get('read_only', True)}",
        f"- default_auth_enabled: {payload.get('default_auth_enabled', False)}",
        f"- default_rbac_enabled: {payload.get('default_rbac_enabled', False)}",
        "",
        "## 权限矩阵",
        "",
        "| Permission | Resource | Action | Allowed roles | Denied roles | 401/403 |",
        "|------------|----------|--------|---------------|--------------|---------|",
    ]
    for row in payload.get("permissions", []):
        lines.append(
            "| {permission} | {resource} | {action} | {allowed} | {denied} | 401 missing token / 403 forbidden |".format(
                permission=row["permission"],
                resource=row["resource"],
                action=row["action"],
                allowed=", ".join(row["allowed_roles"]),
                denied=", ".join(row["denied_roles"]) or "none",
            )
        )
    lines.extend(["", "## 建议动作"])
    for action in payload.get("recommended_actions", []):
        lines.append(f"- {action}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_rbac_permission_matrix(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    rows = _matrix_rows()
    status = _derive_status(rows)
    denied_pairs = [
        {"permission": row["permission"], "role": role}
        for row in rows
        for role in row["denied_roles"]
    ]

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "phase": "v3.6 Phase 16.3",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "real_idp_connected": False,
        "auth_logic_changed": False,
        "require_permission_bypassed": False,
        "tenant_enforcement_enabled": False,
        "default_auth_enabled": bool(settings.auth_enabled),
        "default_rbac_enabled": bool(settings.rbac_enabled),
        "roles": ROLES,
        "role_hierarchy": {role: sorted(values) for role, values in sorted(ROLE_HIERARCHY.items())},
        "permissions": rows,
        "permission_count": len(rows),
        "denied_pair_count": len(denied_pairs),
        "denied_pairs": denied_pairs,
        "review_process": {
            "permission_request": "人工提交权限申请，说明角色、scope、理由、到期时间和复核人。",
            "periodic_review": "企业试点期至少每个迭代复核一次 admin/operator/auditor 权限。",
            "emergency_access": "紧急授权必须记录 owner、expires_at、compensating_controls 和审计证据。",
        },
        "recommended_actions": [
            "继续保持 AUTH_ENABLED、RBAC_ENABLED 默认关闭，保留离线演示路径。",
            "Phase 16.5 前不要宣称 tenant-aware RBAC enforcement 已完成。",
            "后续接入 tenant scope 时，应把 permission + role + scope 三者共同纳入拒绝证据。",
            "所有 403 拒绝路径都应保留审计证据，尤其是 audit/export/tools/call/snapshot/manage。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_rbac_permission_matrix"
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
        "auth_logic_changed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "permission_count": len(rows),
        "denied_pair_count": len(denied_pairs),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.6 RBAC 权限矩阵（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_rbac_permission_matrix(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
