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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_smoke_plan"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
REQUIRED_FALSE_FLAGS = [
    "real_llm_executed",
    "database_connected",
    "redis_connected",
    "external_mcp_connected",
    "migration_executed",
    "business_data_written",
    "audit_data_written",
    "metrics_data_written",
]
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]
BOUNDARY_DECLARATIONS = [
    "只读生成 v4.4 受控真实集成 smoke plan/gate。",
    "默认 fake/offline，不连接真实 LLM、PostgreSQL、Redis 或外部 MCP。",
    "不执行 Alembic migration，不写业务、审计或指标数据。",
    "只输出 env 名称与 present 布尔，不输出 secret 原文。",
    "当前入口仅做计划门禁，不提供真实执行参数。",
    "public_production_direct_launch 始终为 No-Go。",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_present(key: str) -> bool:
    return bool(os.getenv(key))


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_equals(key: str, expected: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() == expected.lower()


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _safe_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "[redacted-secret-like-text]" if _contains_secret_like_text(text) else text


def _execution_flags() -> dict[str, bool]:
    return {flag: False for flag in REQUIRED_FALSE_FLAGS}


def _status_from_conditions(missing_conditions: list[str]) -> str:
    return "partial" if not missing_conditions else "skipped"


def _domain_entry(
    domain_id: str,
    *,
    env_keys: list[str],
    opt_in_conditions: list[tuple[str, bool]],
    planned_smoke_steps: list[str],
    target_secret_env_name: str | None = None,
) -> dict[str, Any]:
    env_present = {key: _env_present(key) for key in env_keys}
    missing_conditions = [condition_id for condition_id, satisfied in opt_in_conditions if not satisfied]

    target_secret_env_present = False
    safe_target_secret_env_name = None
    blocked_by: list[str] = []
    if target_secret_env_name:
        if _contains_secret_like_text(target_secret_env_name):
            blocked_by.append("target_secret_env_name_secret_like")
        else:
            safe_target_secret_env_name = target_secret_env_name
            target_secret_env_present = _env_present(target_secret_env_name)

    status = "blocked" if blocked_by else _status_from_conditions(missing_conditions)
    return {
        "domain_id": domain_id,
        "status": status,
        "opt_in_conditions": [
            {"condition_id": condition_id, "satisfied": satisfied}
            for condition_id, satisfied in opt_in_conditions
        ],
        "env_present": env_present,
        "target_secret_env_name": safe_target_secret_env_name,
        "target_secret_env_present": target_secret_env_present,
        "planned_smoke_steps": planned_smoke_steps,
        "blocked_by": sorted(set(blocked_by)),
        "missing_conditions": sorted(set(missing_conditions)),
        "execution_flags": _execution_flags(),
        "read_only": True,
    }


def _build_domains() -> list[dict[str, Any]]:
    real_llm_secret_env_name = os.getenv("REAL_LLM_API_KEY_ENV")
    return [
        _domain_entry(
            "real_llm",
            env_keys=[
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_MODEL",
                "REAL_LLM_API_KEY_ENV",
            ],
            opt_in_conditions=[
                ("opt_in:REAL_LLM_PREFLIGHT_ENABLED", _env_enabled("REAL_LLM_PREFLIGHT_ENABLED")),
                ("opt_in:REAL_LLM_ACCEPTANCE_ENABLED", _env_enabled("REAL_LLM_ACCEPTANCE_ENABLED")),
                ("opt_in:REAL_LLM_SMOKE_ENABLED", _env_enabled("REAL_LLM_SMOKE_ENABLED")),
                ("env:REAL_LLM_MODEL", _env_present("REAL_LLM_MODEL")),
                ("env:REAL_LLM_API_KEY_ENV", _env_present("REAL_LLM_API_KEY_ENV")),
            ],
            planned_smoke_steps=[
                "校验 provider preflight 配置与模型名。",
                "人工确认 REAL_LLM_API_KEY_ENV 指向的 secret env 已注入。",
                "复核预算、缓存、fallback 与脱敏审计边界。",
                "进入独立 runbook 人工审批，不在本脚本内执行真实请求。",
            ],
            target_secret_env_name=real_llm_secret_env_name,
        ),
        _domain_entry(
            "postgres",
            env_keys=["STORAGE_BACKEND", "DATABASE_URL"],
            opt_in_conditions=[
                ("opt_in:STORAGE_BACKEND_postgres", _env_equals("STORAGE_BACKEND", "postgres")),
                ("env:DATABASE_URL", _env_present("DATABASE_URL")),
            ],
            planned_smoke_steps=[
                "确认 STORAGE_BACKEND=postgres 与 DATABASE_URL 已配置。",
                "复核 deployment guard 与 Store Factory 路径。",
                "人工确认 migration 前置条件，但本脚本不执行 Alembic。",
                "进入受控 staging smoke runbook，不在本脚本内发起连接。",
            ],
        ),
        _domain_entry(
            "redis",
            env_keys=["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_BACKEND"],
            opt_in_conditions=[
                ("opt_in:REDIS_ENABLED", _env_enabled("REDIS_ENABLED")),
                ("env:REDIS_URL", _env_present("REDIS_URL")),
                ("opt_in:RATE_LIMIT_BACKEND_redis", _env_equals("RATE_LIMIT_BACKEND", "redis")),
            ],
            planned_smoke_steps=[
                "确认 REDIS_ENABLED=true、REDIS_URL 与 RATE_LIMIT_BACKEND=redis。",
                "复核 NoopRedisClient fallback 与 deployment guard。",
                "人工准备限流、断连降级与恢复观察点。",
                "进入受控 staging smoke runbook，不在本脚本内发起连接。",
            ],
        ),
        _domain_entry(
            "external_mcp",
            env_keys=[
                "MCP_MODE",
                "MCP_SERVER_COMMAND",
                "MCP_SERVER_COMMAND_ALLOWLIST",
                "MCP_TOOL_ALLOWLIST",
            ],
            opt_in_conditions=[
                ("opt_in:MCP_MODE_real", _env_equals("MCP_MODE", "real")),
                ("env:MCP_SERVER_COMMAND", _env_present("MCP_SERVER_COMMAND")),
                ("env:MCP_SERVER_COMMAND_ALLOWLIST", _env_present("MCP_SERVER_COMMAND_ALLOWLIST")),
                ("env:MCP_TOOL_ALLOWLIST", _env_present("MCP_TOOL_ALLOWLIST")),
            ],
            planned_smoke_steps=[
                "确认 MCP_MODE=real 与 command/tool allowlist 完整。",
                "复核 ToolGateway、PolicyEngine、审批链路与审计链路。",
                "人工确认 stdio lifecycle、timeout 与隔离边界。",
                "进入受控 staging smoke runbook，不在本脚本内启动真实 MCP 进程。",
            ],
        ),
    ]


def _derive_status(domains: list[dict[str, Any]]) -> str:
    statuses = [item["status"] for item in domains]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if all(status == "partial" for status in statuses):
        return "partial"
    return "skipped"


def _build_go_no_go(status: str) -> dict[str, Any]:
    return {
        "combined_staging_gate": "Manual-Review" if status == "partial" else "Needs-Input",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "execute_parameter_available": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 受控真实集成 Smoke Plan/Gate",
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
        f"- migration_executed: {payload.get('migration_executed', False)}",
        f"- business_data_written: {payload.get('business_data_written', False)}",
        f"- audit_data_written: {payload.get('audit_data_written', False)}",
        f"- metrics_data_written: {payload.get('metrics_data_written', False)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## Go/No-Go",
        f"- combined_staging_gate: {payload.get('go_no_go', {}).get('combined_staging_gate', '')}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        f"- execute_parameter_available: {payload.get('go_no_go', {}).get('execute_parameter_available', False)}",
        "",
        "## 域计划",
    ]
    for item in payload.get("domains", []):
        lines.extend(
            [
                f"### {item.get('domain_id', '')}",
                f"- status: {item.get('status', '')}",
                f"- env_present: {json.dumps(item.get('env_present', {}), ensure_ascii=False)}",
                f"- target_secret_env_name: {item.get('target_secret_env_name')}",
                f"- target_secret_env_present: {item.get('target_secret_env_present', False)}",
                f"- blocked_by: {json.dumps(item.get('blocked_by', []), ensure_ascii=False)}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_integration_smoke_plan(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    domains = _build_domains()
    status = _derive_status(domains)
    missing_conditions = sorted(
        {condition for item in domains for condition in item.get("missing_conditions", [])}
    )
    blocked_by = sorted({reason for item in domains for reason in item.get("blocked_by", [])})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.3",
        "phase": "v4.4 Phase 24.4",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "domains": domains,
        "domain_count": len(domains),
        "missing_conditions": missing_conditions,
        "blocked_by": blocked_by,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "go_no_go": _build_go_no_go(status),
        "recommended_next_actions": [
            "补齐目标域的 opt-in 条件并重新生成只读 smoke plan。",
            "条件齐备后进入人工复核与独立 runbook，不能通过本脚本直接执行真实连接。",
            "任何 secret-like 文本命中都必须先脱敏，再进行后续人工评审。",
        ],
        "output_dir": _safe_text(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["blocked_by"] = sorted(set(payload["blocked_by"] + ["output:secret_like_text_detected"]))
        payload["go_no_go"] = _build_go_no_go("blocked")

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_smoke_plan"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "read_only": True,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": _safe_text(output_root),
        "domain_count": len(domains),
        "missing_count": len(payload["missing_conditions"]),
        "blocked_count": len(payload["blocked_by"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.4 受控真实集成 smoke plan/gate 报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_real_integration_smoke_plan(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
