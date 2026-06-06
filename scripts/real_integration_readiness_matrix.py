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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_readiness"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读真实集成落地准备度矩阵",
    "默认 fake/offline，不调用真实 LLM",
    "默认不连接真实 PostgreSQL",
    "默认不连接真实 Redis",
    "默认不启动或连接真实 MCP Server",
    "不执行 Alembic migration",
    "不写业务数据、审计数据或指标数据",
    "仅输出 env name 与 present 布尔值，不输出 secret 原文",
    "缺少 opt-in 条件时必须保留 skipped/partial 语义",
    "不宣称真实 LLM、PostgreSQL、Redis 或 MCP Server 生产验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_presence(keys: list[str]) -> dict[str, dict[str, bool]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_equals(key: str, expected: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() == expected.lower()


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _local_checks(paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {name: {"path": path, "present": _path_exists(path)} for name, path in paths.items()}


def _contains_secret_like_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _component(
    component_id: str,
    name: str,
    *,
    env_keys: list[str],
    opt_in_conditions: list[tuple[str, bool]],
    local_paths: dict[str, str],
    controlled_acceptance_steps: list[str],
    production_gaps: list[str],
) -> dict[str, Any]:
    env = _env_presence(env_keys)
    local = _local_checks(local_paths)
    missing_conditions: list[str] = []

    for condition_id, satisfied in opt_in_conditions:
        if not satisfied:
            missing_conditions.append(condition_id)

    for key, item in local.items():
        if not item["present"]:
            missing_conditions.append(f"local:{key}")

    status = "partial" if not missing_conditions else "skipped"
    return {
        "integration_id": component_id,
        "component_id": component_id,
        "name": name,
        "readiness_status": status,
        "status": status,
        "env": env,
        "local_checks": local,
        "missing_conditions": sorted(set(missing_conditions)),
        "skipped_reasons": sorted(set(missing_conditions)) if status == "skipped" else [],
        "controlled_acceptance_steps": controlled_acceptance_steps,
        "production_gaps": production_gaps,
        "risk_notes": production_gaps,
        "recommended_next_actions": controlled_acceptance_steps,
        "read_only": True,
        "real_llm_executed": False,
        "real_execution": False,
    }


def _build_components() -> list[dict[str, Any]]:
    return [
        _component(
            "real_llm",
            "真实 LLM 受控接入",
            env_keys=[
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_MODEL",
                "REAL_LLM_API_KEY_ENV",
                "LLM_BUDGET_ENABLED",
            ],
            opt_in_conditions=[
                ("opt_in:REAL_LLM_PREFLIGHT_ENABLED", _env_enabled("REAL_LLM_PREFLIGHT_ENABLED")),
                ("opt_in:REAL_LLM_ACCEPTANCE_ENABLED", _env_enabled("REAL_LLM_ACCEPTANCE_ENABLED")),
                ("opt_in:REAL_LLM_SMOKE_ENABLED", _env_enabled("REAL_LLM_SMOKE_ENABLED")),
                ("env:REAL_LLM_MODEL", bool(os.getenv("REAL_LLM_MODEL"))),
                ("env:REAL_LLM_API_KEY_ENV", bool(os.getenv("REAL_LLM_API_KEY_ENV"))),
            ],
            local_paths={
                "preflight": "app/harness/llm/preflight.py",
                "acceptance": "app/harness/llm/acceptance.py",
                "acceptance_gate": "scripts/real_llm_provider_acceptance_gate.py",
                "acceptance_tests": "tests/test_real_llm_provider_acceptance_gate_v373.py",
            },
            controlled_acceptance_steps=[
                "provider preflight no-network",
                "人工确认后开启 network smoke",
                "预算/缓存/fallback 复核",
                "脱敏证据归档",
            ],
            production_gaps=[
                "真实 provider 稳定性需要外部环境证据",
                "默认测试仍不得调用真实 LLM",
            ],
        ),
        _component(
            "postgres",
            "PostgreSQL Store 受控接入",
            env_keys=["STORAGE_BACKEND", "DATABASE_URL"],
            opt_in_conditions=[
                ("opt_in:STORAGE_BACKEND_postgres", _env_equals("STORAGE_BACKEND", "postgres")),
                ("env:DATABASE_URL", bool(os.getenv("DATABASE_URL"))),
            ],
            local_paths={
                "store_factory": "app/storage/factory.py",
                "postgres_user_store": "app/storage/postgres/user_store.py",
                "postgres_task_store": "app/storage/postgres/task_store.py",
                "postgres_approval_store": "app/storage/postgres/approval_store.py",
                "postgres_audit_store": "app/storage/postgres/audit_store.py",
                "postgres_metrics_store": "app/storage/postgres/metrics_store.py",
                "alembic": "alembic.ini",
                "store_redis_drill": "scripts/store_redis_readiness_drill.py",
            },
            controlled_acceptance_steps=[
                "deployment guard",
                "Alembic migration precheck",
                "Store Factory smoke",
                "SQLite fallback 回归",
            ],
            production_gaps=[
                "本矩阵不连接数据库",
                "migration 必须人工审批执行",
            ],
        ),
        _component(
            "redis",
            "Redis 受控接入",
            env_keys=["REDIS_ENABLED", "REDIS_URL"],
            opt_in_conditions=[
                ("opt_in:REDIS_ENABLED", _env_enabled("REDIS_ENABLED")),
                ("env:REDIS_URL", bool(os.getenv("REDIS_URL"))),
            ],
            local_paths={
                "redis_client": "app/cache/redis_client.py",
                "request_guards": "app/core/request_guards.py",
                "deployment_guard": "app/core/deployment_guard.py",
                "store_redis_drill": "scripts/store_redis_readiness_drill.py",
            },
            controlled_acceptance_steps=[
                "Redis health smoke",
                "NoopRedisClient fallback 回归",
                "限流边界复核",
                "多实例限流证据归档",
            ],
            production_gaps=[
                "默认 memory 限流不能代表多实例生产限流",
                "Redis rate limit backend 已具备 opt-in 路径但仍需真实 Redis 验收证据",
                "本矩阵不连接 Redis",
            ],
        ),
        _component(
            "external_mcp",
            "真实 MCP Server 受控接入",
            env_keys=[
                "MCP_MODE",
                "MCP_SERVER_COMMAND",
                "MCP_SERVER_COMMAND_ALLOWLIST",
                "MCP_TOOL_ALLOWLIST",
                "MCP_SERVER_ENV_ALLOWLIST",
                "MCP_SERVER_TIMEOUT_SECONDS",
            ],
            opt_in_conditions=[
                ("opt_in:MCP_MODE_real", _env_equals("MCP_MODE", "real")),
                ("env:MCP_SERVER_COMMAND", bool(os.getenv("MCP_SERVER_COMMAND"))),
                ("env:MCP_SERVER_COMMAND_ALLOWLIST", bool(os.getenv("MCP_SERVER_COMMAND_ALLOWLIST"))),
                ("env:MCP_TOOL_ALLOWLIST", bool(os.getenv("MCP_TOOL_ALLOWLIST"))),
            ],
            local_paths={
                "stdio_client": "app/tools/mcp/stdio_client.py",
                "external_mcp_gate": "scripts/external_mcp_acceptance_gate.py",
                "stdio_tests": "tests/test_mcp_stdio_client_v31.py",
                "external_mcp_tests": "tests/test_external_mcp_acceptance_gate_v372.py",
                "fake_stdio_fixture": "tests/fixtures/fake_mcp_stdio_server.py",
            },
            controlled_acceptance_steps=[
                "stdio initialize",
                "tools/list 映射",
                "allowlist tools/call",
                "超时/stderr/lifecycle hardening",
                "ToolGateway/PolicyEngine/Approval/Audit 复核",
            ],
            production_gaps=[
                "默认 MCP_MODE=fake",
                "真实 MCP Server 必须隔离运行并限制 allowlist",
            ],
        ),
    ]


def _derive_status(components: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in components):
        return "blocked"
    if all(item["status"] == "partial" for item in components):
        return "partial"
    return "skipped"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 真实集成落地准备度矩阵（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- phase: {payload.get('phase', '')}",
        f"- status: {payload.get('status', '')}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        f"- database_connected: {payload.get('database_connected', False)}",
        f"- redis_connected: {payload.get('redis_connected', False)}",
        f"- external_mcp_connected: {payload.get('external_mcp_connected', False)}",
        "",
        "## 组件矩阵",
    ]
    for item in payload.get("integrations", []):
        lines.extend(
            [
                f"### {item.get('name', '')}",
                f"- status: {item.get('readiness_status', '')}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                f"- production_gaps: {json.dumps(item.get('production_gaps', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.extend(["## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_integration_readiness_matrix(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    components = _build_components()
    missing_conditions = sorted({item for component in components for item in component.get("missing_conditions", [])})
    status = _derive_status(components)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.1",
        "phase": "v4.4 Phase 24.1",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "integrations": components,
        "components": components,
        "integration_count": len(components),
        "component_count": len(components),
        "missing_conditions": missing_conditions,
        "skipped_reasons": sorted({item for component in components for item in component.get("skipped_reasons", [])}),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "read_only": True,
        "real_llm_executed": False,
        "provider_network_check_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "mcp_process_started": False,
        "mcp_tools_list_executed": False,
        "mcp_tools_call_executed": False,
        "business_system_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "controlled_internal_pilot": "Needs-Input" if status == "skipped" else "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "recommended_next_actions": [
            "先补齐真实 LLM opt-in 预检证据，再执行真实 smoke。",
            "PostgreSQL/Redis 先通过 deployment guard，再进入受控环境演练。",
            "真实 MCP Server 必须配置 command allowlist 和 env allowlist。",
            "组合 staging runbook 只能消费脱敏证据，不自动批准上线。",
        ],
        "output_dir": str(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_readiness"
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
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "component_count": len(components),
        "integration_count": len(components),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.4 真实集成落地准备度只读矩阵（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_real_integration_readiness_matrix(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
