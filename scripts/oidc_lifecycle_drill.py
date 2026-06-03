from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.auth.oidc_config import build_oidc_status, validate_oidc_settings
from app.core.config import settings

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "oidc_lifecycle_drill"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
OIDC_REQUIRED_ENV = [
    "OIDC_ENABLED",
    "OIDC_ISSUER_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET_ENV",
    "OIDC_REDIRECT_URI",
]

LIFECYCLE_SCENARIOS = [
    {
        "scenario_id": "configuration_preflight",
        "name": "OIDC 配置预检",
        "required_evidence": ["issuer/client_id/redirect_uri/client_secret_env present", "https policy checked"],
    },
    {
        "scenario_id": "token_lifecycle",
        "name": "Token 生命周期演练",
        "required_evidence": ["access token expiry", "invalid token rejection", "role claim mapping"],
    },
    {
        "scenario_id": "logout_session",
        "name": "登出与会话失效演练",
        "required_evidence": ["logout redirect policy", "local session invalidation plan"],
    },
    {
        "scenario_id": "jwks_rotation",
        "name": "JWKS 轮换演练",
        "required_evidence": ["old key rejection", "new key acceptance", "cache refresh boundary"],
    },
    {
        "scenario_id": "client_secret_rotation",
        "name": "client_secret 轮换演练",
        "required_evidence": ["old secret revoked", "new secret injected via env", "no plaintext output"],
    },
    {
        "scenario_id": "failure_paths",
        "name": "失败路径演练",
        "required_evidence": ["issuer unavailable", "redirect mismatch", "role claim missing", "secret missing"],
    },
]

BOUNDARY_DECLARATIONS = [
    "只读 OIDC lifecycle drill plan",
    "仅检查配置键、env name 与 present 布尔状态",
    "不输出 client_secret 或 token 原文",
    "默认不连接真实外部 IdP",
    "默认不执行 OIDC token exchange",
    "不修改 .env 或环境变量",
    "不默认启用 AUTH_ENABLED、RBAC_ENABLED、OIDC_ENABLED",
    "不写业务数据",
    "不执行真实外网 LLM",
    "缺少真实 IdP opt-in 条件时记录为 skipped",
    "不宣称生产级 SSO/OIDC 已完成",
    "不宣称多租户、复杂 BI 全量完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_presence() -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for key in OIDC_REQUIRED_ENV:
        present = bool(os.getenv(key))
        rows[key] = {"present": present}
        if not present:
            missing.append(f"env:{key}")

    secret_env_name = os.getenv("OIDC_CLIENT_SECRET_ENV", "").strip()
    secret_present = bool(secret_env_name and os.getenv(secret_env_name))
    rows["OIDC_CLIENT_SECRET_ENV_TARGET"] = {
        "env_name": secret_env_name,
        "present": secret_present,
    }
    if not secret_present:
        missing.append("env:OIDC_CLIENT_SECRET_ENV_TARGET")

    rows["OIDC_ENABLED_TRUE"] = {"present": _is_true(os.getenv("OIDC_ENABLED"))}
    if not _is_true(os.getenv("OIDC_ENABLED")):
        missing.append("opt_in:OIDC_ENABLED_not_true")
    return rows, sorted(set(missing))


def _scenario_rows(missing_conditions: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in LIFECYCLE_SCENARIOS:
        status = "skipped" if missing_conditions else "planned"
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "name": scenario["name"],
                "status": status,
                "required_evidence": scenario["required_evidence"],
                "token_exchange_executed": False,
                "real_idp_connected": False,
                "missing_conditions": missing_conditions if status == "skipped" else [],
            }
        )
    return rows


def _derive_status(missing_conditions: list[str]) -> str:
    if missing_conditions:
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.6 OIDC lifecycle drill plan（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- real_idp_connected: {payload.get('real_idp_connected', False)}",
        f"- oidc_token_exchange_executed: {payload.get('oidc_token_exchange_executed', False)}",
        "",
        "## 演练场景",
    ]
    for row in payload.get("scenarios", []):
        lines.extend(
            [
                f"### {row['name']}",
                f"- scenario_id: {row['scenario_id']}",
                f"- status: {row['status']}",
                f"- missing_conditions: {json.dumps(row.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_oidc_lifecycle_drill(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    env, env_missing = _env_presence()
    validation = validate_oidc_settings(settings)
    oidc_status = build_oidc_status(settings)
    config_errors = [f"config:{item}" for item in validation.get("errors", [])]
    missing_conditions = sorted(set(env_missing + config_errors))
    scenarios = _scenario_rows(missing_conditions)
    status = _derive_status(missing_conditions)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "phase": "v3.6 Phase 16.4",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "real_idp_connected": False,
        "oidc_token_exchange_executed": False,
        "client_secret_plaintext_output": False,
        "token_plaintext_output": False,
        "default_auth_enabled": bool(settings.auth_enabled),
        "default_rbac_enabled": bool(settings.rbac_enabled),
        "default_oidc_enabled": bool(settings.oidc_enabled),
        "env_presence": env,
        "oidc_status": {
            "enabled": oidc_status["enabled"],
            "issuer_configured": oidc_status["issuer_configured"],
            "client_id_configured": oidc_status["client_id_configured"],
            "redirect_uri_configured": oidc_status["redirect_uri_configured"],
            "client_secret_env": oidc_status["client_secret_env"],
            "client_secret_present": oidc_status["client_secret_present"],
            "role_claim": oidc_status["role_claim"],
            "default_role": oidc_status["default_role"],
            "allowed_roles": oidc_status["allowed_roles"],
            "errors": oidc_status["errors"],
            "warnings": oidc_status["warnings"],
        },
        "missing_conditions": missing_conditions,
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "recommended_actions": [
            "缺少真实 IdP opt-in 条件时保持 skipped，不伪造成 success。",
            "真实 IdP 联调必须另行 opt-in，并产出脱敏证据。",
            "client_secret 轮换仅记录 env name 和 present 布尔状态，不粘贴 secret 原文。",
            "JWKS 与 token 生命周期验收完成前，不宣称生产级 SSO/OIDC 已完成。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_oidc_lifecycle_drill"
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
        "oidc_token_exchange_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "missing_count": len(missing_conditions),
        "scenario_count": len(scenarios),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.6 OIDC 生命周期演练计划（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_oidc_lifecycle_drill(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
