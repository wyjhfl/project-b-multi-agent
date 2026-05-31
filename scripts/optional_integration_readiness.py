from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "optional_integration_readiness"

BOUNDARY_DECLARATIONS = [
    "只读集成准备度矩阵",
    "仅检查配置存在性和本地可验证条件",
    "不读取或输出真实 secret 值",
    "不调用真实外网 LLM",
    "不连接真实外部 MCP",
    "不要求默认配置启用 auth/RBAC/Redis/PostgreSQL",
    "默认 fake/offline",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_present(keys: list[str]) -> dict[str, dict[str, bool]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _missing_from_presence(presence: dict[str, dict[str, bool]]) -> list[str]:
    return [key for key, item in presence.items() if not item.get("present", False)]


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _integration(
    integration_id: str,
    name: str,
    *,
    env_keys: list[str] | None = None,
    local_checks: dict[str, str] | None = None,
    risk_notes: list[str] | None = None,
    recommended_next_actions: list[str] | None = None,
) -> dict[str, Any]:
    env_presence = _env_present(env_keys or [])
    missing_conditions = _missing_from_presence(env_presence)
    local_results = {key: {"path": path, "present": _path_exists(path)} for key, path in (local_checks or {}).items()}
    for key, item in local_results.items():
        if not item["present"]:
            missing_conditions.append(f"local:{key}")

    readiness_status = "ready" if not missing_conditions else "skipped"
    return {
        "integration_id": integration_id,
        "name": name,
        "readiness_status": readiness_status,
        "env": env_presence,
        "local_checks": local_results,
        "missing_conditions": missing_conditions,
        "skipped_reasons": missing_conditions if readiness_status == "skipped" else [],
        "risk_notes": risk_notes or [],
        "recommended_next_actions": recommended_next_actions or [],
        "read_only": True,
        "real_llm_executed": False,
    }


def _build_integrations() -> list[dict[str, Any]]:
    return [
        _integration(
            "real_llm",
            "真实 LLM opt-in readiness",
            env_keys=[
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
                "REAL_LLM_MODEL",
                "REAL_LLM_API_KEY_ENV",
            ],
            local_checks={"real_llm_smoke_script": "scripts/real_llm_smoke.ps1"},
            risk_notes=["真实 LLM smoke 仅为 opt-in 验收，不等于生产验收完成。"],
            recommended_next_actions=["缺少 opt-in 条件时保持 skipped，不执行真实外网 LLM。"],
        ),
        _integration(
            "oidc",
            "OIDC readiness",
            env_keys=["OIDC_ENABLED", "OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET_ENV", "OIDC_REDIRECT_URI"],
            local_checks={"oidc_drill_doc": "docs/oidc_minimal_idp_drill_v31.md"},
            risk_notes=["OIDC 当前是最小演练边界，不宣称生产级 SSO/OIDC 完成。"],
            recommended_next_actions=["仅输出 env present 状态，不输出 client secret 原文。"],
        ),
        _integration(
            "external_mcp",
            "外部 MCP readiness",
            env_keys=["MCP_MODE", "MCP_SERVER_COMMAND", "MCP_TOOL_ALLOWLIST"],
            local_checks={"stdio_client": "app/tools/mcp/stdio_client.py", "fake_stdio_fixture": "tests/fixtures/fake_mcp_stdio_server.py"},
            risk_notes=["默认 MCP_MODE=fake；真实外部 MCP 需显式 command 与 allowlist。"],
            recommended_next_actions=["未满足真实 MCP 条件时使用 fake/offline fixture。"],
        ),
        _integration(
            "postgres",
            "PostgreSQL readiness",
            env_keys=["STORAGE_BACKEND", "DATABASE_URL"],
            local_checks={"prod_compose": "docker-compose.prod.yml", "alembic_ini": "alembic.ini"},
            risk_notes=["默认 storage_backend=sqlite；PostgreSQL Store 需显式配置启用。"],
            recommended_next_actions=["企业试点启用前运行 deployment guard 与迁移预检。"],
        ),
        _integration(
            "redis",
            "Redis readiness",
            env_keys=["REDIS_ENABLED", "REDIS_URL"],
            local_checks={"compose": "docker-compose.yml"},
            risk_notes=["默认 redis_enabled=false 时 NoopRedisClient 不抛异常。"],
            recommended_next_actions=["多实例限流需要 Redis 或网关级限流。"],
        ),
        _integration(
            "frontend_build_network",
            "前端 build/network dependency readiness",
            env_keys=["NEXT_PUBLIC_API_BASE_URL"],
            local_checks={"package_lock": "frontend/package-lock.json", "next_config": "frontend/next.config.ts"},
            risk_notes=["前端 build 依赖 node_modules；网络安装依赖不等于运行时真实外部集成。"],
            recommended_next_actions=["默认演示保持离线后端 fake/offline 路径。"],
        ),
        _integration(
            "deployment_guard",
            "Deployment guard readiness",
            env_keys=["APP_ENV", "AUTH_ENABLED", "RBAC_ENABLED", "JWT_SECRET", "DATABASE_URL", "REDIS_URL"],
            local_checks={"deployment_guard": "app/core/deployment_guard.py", "deployment_api": "app/api/deployment.py"},
            risk_notes=["生产门禁返回结构化结果，不应抛 500。"],
            recommended_next_actions=["prod compose 注入临时变量后复核 config，通过后清理临时变量。"],
        ),
        _integration(
            "audit_export_redaction",
            "Audit export/redaction readiness",
            env_keys=[],
            local_checks={"audit_api": "app/api/audit.py", "structured_logging": "app/core/structured_logging.py"},
            risk_notes=["审计导出默认脱敏，不导出 prompt 原文、密钥原文、连接串密码原文。"],
            recommended_next_actions=["复核 JSONL 导出边界与脱敏测试。"],
        ),
    ]


def _derive_status(integrations: list[dict[str, Any]]) -> str:
    if all(item["readiness_status"] == "ready" for item in integrations):
        return "ready"
    if any(item["readiness_status"] == "ready" for item in integrations):
        return "partial"
    return "skipped"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.4 可选集成准备度矩阵（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- readiness_status: {payload.get('readiness_status', '')}",
        "",
        "## Integrations",
    ]
    for item in payload.get("integrations", []):
        lines.extend(
            [
                f"### {item.get('name', '')}",
                f"- readiness_status: {item.get('readiness_status', '')}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.extend(["## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_optional_integration_readiness(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    integrations = _build_integrations()
    missing_conditions = sorted({missing for item in integrations for missing in item.get("missing_conditions", [])})
    skipped_reasons = sorted({reason for item in integrations for reason in item.get("skipped_reasons", [])})
    readiness_status = _derive_status(integrations)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.4.0",
        "integrations": integrations,
        "readiness_status": readiness_status,
        "missing_conditions": missing_conditions,
        "skipped_reasons": skipped_reasons,
        "risk_notes": [note for item in integrations for note in item.get("risk_notes", [])],
        "recommended_next_actions": [action for item in integrations for action in item.get("recommended_next_actions", [])],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "read_only": True,
        "real_llm_executed": False,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_optional_integration_readiness"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": readiness_status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "integration_count": len(integrations),
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.4 可选集成准备度只读矩阵（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_optional_integration_readiness(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
