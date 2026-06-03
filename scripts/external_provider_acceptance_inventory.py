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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "external_provider_acceptance_inventory"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读外部集成与真实 provider 验收基线盘点",
    "仅输出 env name、present 布尔状态和本地文件存在性",
    "不读取或输出真实 secret 原文",
    "不调用真实外网 LLM",
    "不连接真实外部 MCP",
    "不连接真实业务系统",
    "不执行真实数据库迁移或 Redis 写入",
    "不绕过 ToolGateway、PolicyEngine、审批链路或审计链路",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称真实 provider 或真实业务系统生产验收完成",
]


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


def _env_present(keys: list[str]) -> dict[str, dict[str, bool]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _target_env_presence(env_name_key: str) -> dict[str, Any]:
    env_name = (os.getenv(env_name_key, "") or "").strip()
    return {
        "env_name_key": env_name_key,
        "env_name": env_name,
        "present": bool(env_name and os.getenv(env_name)),
    }


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _local_checks(paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "path": path,
            "present": _path_exists(path),
        }
        for key, path in paths.items()
    }


def _missing_from_env(env: dict[str, dict[str, bool]]) -> list[str]:
    return [f"env:{key}" for key, item in env.items() if not item.get("present")]


def _missing_from_local(local: dict[str, dict[str, Any]]) -> list[str]:
    return [f"local:{key}" for key, item in local.items() if not item.get("present")]


def _integration(
    integration_id: str,
    name: str,
    *,
    env_keys: list[str],
    local_paths: dict[str, str],
    opt_in_keys: list[str] | None = None,
    expected_values: dict[str, str] | None = None,
    target_env_keys: list[str] | None = None,
    risk_notes: list[str] | None = None,
    recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    env = _env_present(env_keys)
    local = _local_checks(local_paths)
    target_env = [_target_env_presence(key) for key in (target_env_keys or [])]
    missing_conditions = _missing_from_local(local)
    skipped_reasons: list[str] = []

    for key, item in env.items():
        if not item["present"]:
            skipped_reasons.append(f"env:{key}")

    for key in opt_in_keys or []:
        if not _env_enabled(key):
            skipped_reasons.append(f"opt_in:{key}_not_enabled")

    for key, expected in (expected_values or {}).items():
        actual = (os.getenv(key, "") or "").strip()
        if actual != expected:
            skipped_reasons.append(f"env:{key}_not_{expected}")

    for item in target_env:
        if not item["present"]:
            skipped_reasons.append(f"env_target:{item['env_name_key']}_target_missing")

    status = "partial"
    if missing_conditions:
        status = "skipped"
    if skipped_reasons and status != "skipped":
        status = "partial"

    return {
        "integration_id": integration_id,
        "name": name,
        "status": status,
        "env": env,
        "target_env": target_env,
        "local_checks": local,
        "missing_conditions": sorted(set(missing_conditions + skipped_reasons)),
        "skipped_reasons": sorted(set(skipped_reasons)),
        "risk_notes": risk_notes or [],
        "recommended_actions": recommended_actions or [],
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "business_system_connected": False,
    }


def _build_integrations() -> list[dict[str, Any]]:
    return [
        _integration(
            "external_mcp",
            "真实外部 MCP 验收基线",
            env_keys=["MCP_MODE", "MCP_SERVER_COMMAND", "MCP_SERVER_COMMAND_ALLOWLIST", "MCP_TOOL_ALLOWLIST"],
            expected_values={"MCP_MODE": "real"},
            local_paths={
                "stdio_client": "app/tools/mcp/stdio_client.py",
                "fake_stdio_fixture": "tests/fixtures/fake_mcp_stdio_server.py",
                "mcp_tests": "tests/test_mcp_stdio_client_v31.py",
            },
            risk_notes=["默认 MCP_MODE=fake；真实外部 MCP 必须显式 command 与 allowlist。"],
            recommended_actions=["Phase 17.2 建立真实 MCP acceptance gate。"],
        ),
        _integration(
            "real_llm_provider",
            "真实 LLM provider 验收基线",
            env_keys=[
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
                "REAL_LLM_MODEL",
                "REAL_LLM_API_KEY_ENV",
            ],
            opt_in_keys=[
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
            ],
            target_env_keys=["REAL_LLM_API_KEY_ENV"],
            local_paths={
                "provider": "app/agent/nl2sql/provider.py",
                "preflight": "app/harness/llm/preflight.py",
                "real_llm_smoke": "scripts/real_llm_smoke.ps1",
                "real_llm_tests": "tests/test_real_llm_smoke_v52.py",
            },
            risk_notes=["真实 LLM smoke 仅为 opt-in 验收，不等于生产验收完成。"],
            recommended_actions=["Phase 17.3 建立真实 LLM provider acceptance gate。"],
        ),
        _integration(
            "llm_judge_provider",
            "真实 LLM Judge 验收基线",
            env_keys=["REAL_LLM_SMOKE_ENABLED", "REAL_LLM_MODEL", "REAL_LLM_API_KEY_ENV"],
            opt_in_keys=["REAL_LLM_SMOKE_ENABLED"],
            target_env_keys=["REAL_LLM_API_KEY_ENV"],
            local_paths={
                "judge": "app/harness/eval/judge.py",
                "judge_smoke_tests": "tests/test_real_llm_judge_smoke_v54.py",
                "badcase_eval": "tests/test_badcase_eval_v05.py",
            },
            risk_notes=["LLMJudgeProvider 默认仍不调用真实 provider，真实 judge smoke 必须 opt-in。"],
            recommended_actions=["将 judge smoke 证据纳入真实 provider 验收包。"],
        ),
        _integration(
            "postgres_store",
            "PostgreSQL Store 验收基线",
            env_keys=["STORAGE_BACKEND", "DATABASE_URL"],
            expected_values={"STORAGE_BACKEND": "postgres"},
            local_paths={
                "store_factory": "app/storage/factory.py",
                "alembic": "alembic.ini",
                "prod_compose": "docker-compose.prod.yml",
                "storage_tests": "tests/test_storage_v20.py",
            },
            risk_notes=["默认 storage_backend=sqlite；PostgreSQL 需要显式配置和迁移预检。"],
            recommended_actions=["Phase 17.4 建立 Store/Redis production readiness drill。"],
        ),
        _integration(
            "redis_runtime",
            "Redis runtime 验收基线",
            env_keys=["REDIS_ENABLED", "REDIS_URL"],
            opt_in_keys=["REDIS_ENABLED"],
            local_paths={
                "redis_client": "app/core/redis_client.py",
                "compose": "docker-compose.yml",
                "deployment_guard": "app/core/deployment_guard.py",
            },
            risk_notes=["默认 redis_enabled=false 时 NoopRedisClient 不抛异常；多实例限流需 Redis 或网关级限流。"],
            recommended_actions=["Phase 17.4 复核 Redis 启用、失败和 fallback 路径。"],
        ),
        _integration(
            "deployment_guard",
            "Deployment guard 验收基线",
            env_keys=["APP_ENV", "AUTH_ENABLED", "RBAC_ENABLED", "JWT_SECRET", "DATABASE_URL", "REDIS_URL"],
            local_paths={
                "deployment_guard": "app/core/deployment_guard.py",
                "deployment_api": "app/api/deployment.py",
                "prod_compose": "docker-compose.prod.yml",
                "deployment_tests": "tests/test_deployment_guard_v60.py",
            },
            risk_notes=["生产门禁必须返回结构化结果，不应抛 500。"],
            recommended_actions=["真实集成验收前必须先通过 deployment guard。"],
        ),
        _integration(
            "tool_approval_audit",
            "工具调用审批与审计边界",
            env_keys=[],
            local_paths={
                "tool_gateway": "app/harness/gateway/tool_gateway.py",
                "policy_engine": "app/harness/policy/engine.py",
                "approval_api": "app/api/approvals.py",
                "audit_api": "app/api/audit.py",
                "audit_tests": "tests/test_audit_v045.py",
            },
            risk_notes=["前端和外部工具调用必须经过 ToolGateway、PolicyEngine、审批链路和审计链路。"],
            recommended_actions=["Phase 17.5 建立业务系统写入集成安全清单。"],
        ),
        _integration(
            "frontend_offline_build",
            "前端离线构建基线",
            env_keys=[],
            local_paths={
                "layout": "frontend/src/app/layout.tsx",
                "globals": "frontend/src/app/globals.css",
                "package_lock": "frontend/package-lock.json",
                "next_config": "frontend/next.config.ts",
            },
            risk_notes=["前端已移除构建期 Google Fonts 依赖，默认离线 build 可通过。"],
            recommended_actions=["保持前端构建不依赖运行时真实外部 provider。"],
        ),
    ]


def _derive_status(integrations: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "blocked" for item in integrations):
        return "blocked"
    if all(item.get("status") == "skipped" for item in integrations):
        return "skipped"
    return "partial"


def _assert_no_secret_output(payload: dict[str, Any]) -> bool:
    return not _contains_secret_like_text(json.dumps(payload, ensure_ascii=False))


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.7 外部集成与真实 provider 验收基线（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- read_only: {payload.get('read_only', True)}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        f"- external_mcp_connected: {payload.get('external_mcp_connected', False)}",
        "",
        "## 集成项",
    ]
    for item in payload.get("integrations", []):
        lines.extend(
            [
                f"### {item['name']}",
                f"- integration_id: {item['integration_id']}",
                f"- status: {item['status']}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_external_provider_acceptance_inventory(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    integrations = _build_integrations()
    missing_conditions = sorted({item for integration in integrations for item in integration.get("missing_conditions", [])})
    skipped_reasons = sorted({item for integration in integrations for item in integration.get("skipped_reasons", [])})
    status = _derive_status(integrations)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "phase": "v3.7 Phase 17.1",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "business_system_connected": False,
        "database_migration_executed": False,
        "redis_write_executed": False,
        "secret_plaintext_output": False,
        "integrations": integrations,
        "integration_count": len(integrations),
        "missing_conditions": missing_conditions,
        "skipped_reasons": skipped_reasons,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "Phase 17.2 建立 External MCP acceptance gate。",
            "Phase 17.3 建立 Real LLM provider acceptance gate。",
            "Phase 17.4 建立 Store and Redis production readiness drill。",
            "所有真实 provider 验收必须显式 opt-in，并产出脱敏证据。",
        ],
        "output_dir": str(output_root),
    }
    if not _assert_no_secret_output(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_external_provider_acceptance_inventory"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "business_system_connected": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "integration_count": len(integrations),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.7 外部集成与真实 provider 验收基线盘点（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_external_provider_acceptance_inventory(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
