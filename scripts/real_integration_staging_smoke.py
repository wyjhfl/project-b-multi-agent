from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
DOMAIN_IDS = ["real_llm", "postgres", "redis", "external_mcp"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]
PLACEHOLDER_PATTERN = re.compile(r"^<[^>]+>$")
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}

DOMAIN_SPECS = {
    "real_llm": {
        "execute_opt_in": "REAL_LLM_STAGING_SMOKE_EXECUTE",
        "required_conditions": [
            ("REAL_LLM_PREFLIGHT_ENABLED", "enabled"),
            ("REAL_LLM_ACCEPTANCE_ENABLED", "enabled"),
            ("REAL_LLM_SMOKE_ENABLED", "enabled"),
            ("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "enabled"),
            ("REAL_LLM_MODEL", "present"),
            ("REAL_LLM_API_KEY_ENV", "target_present"),
        ],
        "execution_flag": "real_llm_executed",
    },
    "postgres": {
        "execute_opt_in": "POSTGRES_STAGING_SMOKE_EXECUTE",
        "required_conditions": [
            ("STORAGE_BACKEND", "equals:postgres"),
            ("DATABASE_URL", "present"),
        ],
        "execution_flag": "database_connected",
    },
    "redis": {
        "execute_opt_in": "REDIS_STAGING_SMOKE_EXECUTE",
        "required_conditions": [
            ("REDIS_ENABLED", "enabled"),
            ("REDIS_URL", "present"),
            ("RATE_LIMIT_BACKEND", "equals:redis"),
        ],
        "execution_flag": "redis_connected",
    },
    "external_mcp": {
        "execute_opt_in": "MCP_STAGING_SMOKE_EXECUTE",
        "required_conditions": [
            ("MCP_MODE", "equals:real"),
            ("MCP_SERVER_COMMAND", "present"),
            ("MCP_SERVER_COMMAND_ALLOWLIST", "present"),
            ("MCP_TOOL_ALLOWLIST", "present"),
        ],
        "execution_flag": "external_mcp_connected",
    },
}

BOUNDARY_DECLARATIONS = [
    "受控真实集成 staging smoke 编排入口。",
    "默认 dry-run，不连接真实 LLM、PostgreSQL、Redis 或 MCP Server。",
    "只有命令行 --execute 与 REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true 同时满足，且单域 opt-in 完整时，才允许调用对应 smoke 执行器。",
    "不读取或输出 secret、token、API key、DATABASE_URL、REDIS_URL 或 MCP command 原文。",
    "本脚本不执行 Alembic migration，不写业务、审计或指标数据。",
    "真实执行结果只能作为 staging 证据，不能自动宣称生产验收完成。",
    "public_production_direct_launch 始终 No-Go。",
]


@dataclass
class SmokeExecutionResult:
    status: str
    evidence: dict[str, Any]
    warnings: list[str] | None = None
    errors: list[str] | None = None


SmokeExecutor = Callable[[str], SmokeExecutionResult]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like_text(key) or _contains_secret_like_text(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like_text(item) for item in value)
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>")
                if candidate.lower() in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _safe_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "[redacted-secret-like-text]" if _contains_secret_like_text(text) else text


def _sanitize_for_output(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like_text(value) else value
    if isinstance(value, list):
        return [_sanitize_for_output(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_for_output(item) for key, item in value.items()}
    return value


def _env_value(key: str) -> str:
    return str(os.getenv(key, "") or "").strip()


def _env_present(key: str) -> bool:
    value = _env_value(key)
    return bool(value and not PLACEHOLDER_PATTERN.match(value))


def _env_enabled(key: str) -> bool:
    return _env_value(key).lower() in {"1", "true", "yes", "on"}


def _condition_satisfied(key: str, rule: str) -> bool:
    if rule == "present":
        return _env_present(key)
    if rule == "enabled":
        return _env_enabled(key)
    if rule == "target_present":
        target_name = _env_value(key)
        target_value = str(os.getenv(target_name, "") or "").strip() if target_name else ""
        return bool(
            target_name
            and not _contains_secret_like_text(target_name)
            and target_value
            and not PLACEHOLDER_PATTERN.match(target_value)
        )
    if rule.startswith("equals:"):
        return _env_value(key).lower() == rule.split(":", 1)[1].lower()
    return False


def _condition_id(key: str, rule: str) -> str:
    if rule == "present":
        return f"env:{key}"
    if rule == "enabled":
        return f"opt_in:{key}"
    if rule == "target_present":
        return f"env_target:{key}"
    if rule.startswith("equals:"):
        return f"opt_in:{key}_{rule.split(':', 1)[1]}"
    return f"condition:{key}:{rule}"


def _env_presence_for_domain(domain_id: str) -> dict[str, bool]:
    keys = [key for key, _ in DOMAIN_SPECS[domain_id]["required_conditions"]]
    keys.append(str(DOMAIN_SPECS[domain_id]["execute_opt_in"]))
    return {key: _env_present(key) for key in keys}


def _required_env_for_domain(domain_id: str) -> list[str]:
    if domain_id == "real_llm":
        return [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
            "REAL_LLM_PREFLIGHT_ENABLED=true",
            "REAL_LLM_ACCEPTANCE_ENABLED=true",
            "REAL_LLM_SMOKE_ENABLED=true",
            "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
            "REAL_LLM_PROVIDER=litellm",
            "REAL_LLM_MODEL=mimo-v2.5-pro",
            "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1",
            "REAL_LLM_API_KEY_ENV=XIAOMI_LLM_API_KEY",
            "XIAOMI_LLM_API_KEY=<secret-managed-token>",
        ]
    if domain_id == "postgres":
        return [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "POSTGRES_STAGING_SMOKE_EXECUTE=true",
            "STORAGE_BACKEND=postgres",
            "DATABASE_URL=<secret-managed-url>",
        ]
    if domain_id == "redis":
        return [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "REDIS_STAGING_SMOKE_EXECUTE=true",
            "REDIS_ENABLED=true",
            "REDIS_URL=<secret-managed-url>",
            "RATE_LIMIT_BACKEND=redis",
        ]
    if domain_id == "external_mcp":
        return [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "MCP_STAGING_SMOKE_EXECUTE=true",
            "MCP_MODE=real",
            "MCP_SERVER_COMMAND=<approved-command>",
            "MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>",
            "MCP_TOOL_ALLOWLIST=<approved-tools>",
        ]
    return []


def _domain_preflight_summary(domain: dict[str, Any]) -> dict[str, Any]:
    evidence = domain.get("evidence") if isinstance(domain.get("evidence"), dict) else {}
    env_present = evidence.get("env_present") if isinstance(evidence.get("env_present"), dict) else {}
    missing = domain.get("missing_conditions") if isinstance(domain.get("missing_conditions"), list) else []
    return {
        "domain_id": domain.get("domain_id"),
        "status": domain.get("status"),
        "execution_allowed": bool(domain.get("execution_allowed", False)),
        "execution_invoked": bool(domain.get("execution_invoked", False)),
        "ready_for_execute": bool(domain.get("execution_allowed", False)),
        "missing_count": len(missing),
        "env_present": {str(key): bool(value) for key, value in env_present.items()},
        "required_env": _required_env_for_domain(str(domain.get("domain_id") or "")),
        "next_action": "补齐本域 required_env 后重新执行 real_integration_staging_smoke.py --execute。",
    }


def _default_executor(domain_id: str) -> SmokeExecutionResult:
    try:
        if domain_id == "real_llm":
            from app.harness.llm.preflight import run_llm_provider_preflight

            result = run_llm_provider_preflight(perform_network_check=True)
            data = result.to_dict()
            status = "success" if data.get("status") == "passed" else "failed"
            return SmokeExecutionResult(
                status=status,
                evidence={
                    "preflight_status": data.get("status"),
                    "provider": data.get("provider"),
                    "model_present": bool(data.get("model")),
                    "api_key_env": data.get("api_key_env"),
                    "api_key_present": data.get("api_key_present"),
                    "network_check_executed": data.get("network_check_executed"),
                    "latency_ms": data.get("latency_ms"),
                    "check_count": len(data.get("checks", [])),
                    "error_count": len(data.get("errors", [])),
                    "warning_count": len(data.get("warnings", [])),
                },
                warnings=list(data.get("warnings", [])),
                errors=list(data.get("errors", [])),
            )

        if domain_id == "postgres":
            from app.storage.database import check_database_health

            result = check_database_health()
            status = "success" if result.get("status") == "ok" and result.get("backend") == "postgres" else "failed"
            return SmokeExecutionResult(
                status=status,
                evidence={
                    "health_status": result.get("status"),
                    "backend": result.get("backend"),
                    "error_type": "present" if result.get("error") else None,
                },
                errors=["database_health_error"] if result.get("error") else [],
            )

        if domain_id == "redis":
            from app.cache.redis_client import check_redis_health

            result = check_redis_health()
            status = "success" if result.get("status") == "ok" and result.get("backend") == "redis" else "failed"
            return SmokeExecutionResult(
                status=status,
                evidence={
                    "health_status": result.get("status"),
                    "backend": result.get("backend"),
                    "error_type": "present" if result.get("error") else None,
                },
                errors=["redis_health_error"] if result.get("error") else [],
            )

        if domain_id == "external_mcp":
            from app.harness.gateway.tool_gateway import ToolGateway
            from app.tools.mcp.stdio_client import StdioMCPClient

            client = StdioMCPClient(
                server_name="staging-smoke",
                command=_env_value("MCP_SERVER_COMMAND"),
                args=_env_value("MCP_SERVER_ARGS"),
                timeout_seconds=float(_env_value("MCP_SERVER_TIMEOUT_SECONDS") or "10"),
                workdir=_env_value("MCP_SERVER_WORKDIR"),
                env_allowlist=_env_value("MCP_SERVER_ENV_ALLOWLIST"),
                command_allowlist=_env_value("MCP_SERVER_COMMAND_ALLOWLIST"),
            )
            try:
                gateway = ToolGateway()
                gateway.register_mcp_server(
                    "staging-smoke",
                    client,
                    tool_allowlist=_env_value("MCP_TOOL_ALLOWLIST"),
                )
                tools = gateway.discover_mcp_tools("staging-smoke")
                health = client.get_health()
                allowed_tool_names = [tool.tool_name for tool in tools]
                call_executed = False
                call_success = False
                if tools:
                    record = gateway.call(tools[0].tool_name, {})
                    call_executed = True
                    call_success = bool(record.success)
                return SmokeExecutionResult(
                    status="success" if tools and (not call_executed or call_success) else "failed",
                    evidence={
                        "tools_list_executed": True,
                        "tool_count": len(tools),
                        "tool_allowlist_enforced": True,
                        "allowed_tool_names": allowed_tool_names,
                        "gateway_call_executed": call_executed,
                        "gateway_call_success": call_success,
                        "process_started": bool(health.get("started")),
                        "initialized": bool(health.get("initialized")),
                        "failure_count": int(health.get("failure_count", 0) or 0),
                    },
                    errors=[] if tools and (not call_executed or call_success) else ["mcp_gateway_allowlist_call_failed"],
                )
            finally:
                client.close()

        return SmokeExecutionResult(
            status="blocked",
            evidence={"executor": "unsupported_domain", "domain_id": domain_id},
            errors=["unsupported_domain"],
        )
    except Exception as exc:
        return SmokeExecutionResult(
            status="failed",
            evidence={"exception_type": exc.__class__.__name__},
            errors=[f"{domain_id}_smoke_exception:{exc.__class__.__name__}"],
        )


def _domain_plan(
    domain_id: str,
    *,
    execute_requested: bool,
    global_execute_enabled: bool,
    executor: SmokeExecutor,
) -> dict[str, Any]:
    spec = DOMAIN_SPECS[domain_id]
    missing_conditions = [
        _condition_id(key, rule)
        for key, rule in spec["required_conditions"]
        if not _condition_satisfied(key, rule)
    ]
    domain_execute_enabled = _env_enabled(str(spec["execute_opt_in"]))
    execution_allowed = execute_requested and global_execute_enabled and domain_execute_enabled and not missing_conditions
    execution_requested_but_blocked = execute_requested and not execution_allowed

    status = "skipped"
    evidence: dict[str, Any] = {
        "env_present": _env_presence_for_domain(domain_id),
        "execute_requested": execute_requested,
        "global_execute_enabled": global_execute_enabled,
        "domain_execute_enabled": domain_execute_enabled,
        "execution_allowed": execution_allowed,
        "execution_invoked": False,
    }
    warnings: list[str] = []
    errors: list[str] = []

    if not execute_requested:
        status = "skipped"
        missing_conditions = sorted(set(missing_conditions + ["cli:--execute_not_requested"]))
    elif execution_requested_but_blocked:
        status = "blocked"
        if not global_execute_enabled:
            missing_conditions.append("opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED")
        if not domain_execute_enabled:
            missing_conditions.append(f"opt_in:{spec['execute_opt_in']}")
    else:
        result = executor(domain_id)
        status = result.status if result.status in STATUS_VOCABULARY else "failed"
        if _contains_secret_like_text(result.evidence):
            status = "blocked"
            errors.append("executor_output_secret_like_text_detected")
        evidence.update(_sanitize_for_output(result.evidence))
        evidence["execution_invoked"] = True
        warnings.extend(result.warnings or [])
        errors.extend(result.errors or [])

    result = {
        "domain_id": domain_id,
        "status": status,
        "missing_conditions": sorted(set(missing_conditions)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "execution_allowed": execution_allowed,
        "execution_invoked": bool(evidence.get("execution_invoked")),
        "execution_flag": spec["execution_flag"],
        "evidence": evidence,
    }
    result["preflight"] = _domain_preflight_summary(result)
    return result


def _derive_status(domains: list[dict[str, Any]]) -> str:
    statuses = [item["status"] for item in domains]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if any(status == "failed" for status in statuses):
        return "failed"
    if all(status == "success" for status in statuses):
        return "success"
    if any(status in {"success", "partial"} for status in statuses):
        return "partial"
    return "skipped"


def _execution_flags(domains: list[dict[str, Any]]) -> dict[str, bool]:
    flags = {
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    for item in domains:
        if item["status"] == "success" and item.get("execution_invoked"):
            flags[item["execution_flag"]] = True
    return flags


def _preflight_summary(domains: list[dict[str, Any]]) -> dict[str, Any]:
    domain_preflights = [
        item.get("preflight") for item in domains if isinstance(item.get("preflight"), dict)
    ]
    ready_domains = [item["domain_id"] for item in domain_preflights if item.get("ready_for_execute")]
    return {
        "ready_domain_count": len(ready_domains),
        "domain_count": len(domain_preflights),
        "ready_domains": ready_domains,
        "blocked_domain_count": sum(1 for item in domains if item.get("status") == "blocked"),
        "failed_domain_count": sum(1 for item in domains if item.get("status") == "failed"),
        "all_requested_domains_ready_for_execute": len(ready_domains) == len(domain_preflights) and bool(domain_preflights),
        "domains": domain_preflights,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 真实集成 staging smoke（受控入口）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- phase: {payload.get('phase', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute_requested: {payload.get('execute_requested', False)}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        "",
        "## 域结果",
    ]
    for item in payload.get("domains", []):
        lines.extend(
            [
                f"### {item.get('domain_id', '')}",
                f"- status: {item.get('status', '')}",
                f"- execution_allowed: {item.get('execution_allowed', False)}",
                f"- execution_invoked: {item.get('execution_invoked', False)}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_integration_staging_smoke(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
    domains: list[str] | None = None,
    executor: SmokeExecutor | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    global_execute_enabled = _env_enabled("REAL_INTEGRATION_STAGING_SMOKE_ENABLED")
    smoke_executor = executor or _default_executor
    requested_domains = domains or DOMAIN_IDS
    invalid_domains = sorted({item for item in requested_domains if item not in DOMAIN_IDS})
    effective_domain_ids = [item for item in requested_domains if item in DOMAIN_IDS]
    domain_results = [
        _domain_plan(
            domain_id,
            execute_requested=execute,
            global_execute_enabled=global_execute_enabled,
            executor=smoke_executor,
        )
        for domain_id in effective_domain_ids
    ]
    status = "blocked" if invalid_domains or not effective_domain_ids else _derive_status(domain_results)
    flags = _execution_flags(domain_results)
    preflight_summary = _preflight_summary(domain_results)
    missing_conditions = sorted(
        {item for domain in domain_results for item in domain.get("missing_conditions", [])}
        | {f"domain:{item}:unsupported" for item in invalid_domains}
        | ({"domain:none_selected"} if not effective_domain_ids else set())
    )
    warnings = sorted({item for domain in domain_results for item in domain.get("warnings", [])})
    errors = sorted(
        {item for domain in domain_results for item in domain.get("errors", [])}
        | {f"unsupported_domain:{item}" for item in invalid_domains}
    )

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.6",
        "phase": "v4.4 Phase 24.7 Controlled Real Integration Staging Smoke",
        "mode": "execute_opt_in" if execute else "dry_run_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "execution_mode": "read_only_smoke",
        "execute_requested": execute,
        "global_execute_enabled": global_execute_enabled,
        "requested_domains": requested_domains,
        "invalid_domains": invalid_domains,
        "domains": domain_results,
        "domain_count": len(domain_results),
        "preflight_summary": preflight_summary,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "errors": errors,
        "secret_plaintext_output": False,
        **flags,
        "go_no_go": {
            "combined_staging_gate": "Manual-Review" if status in {"success", "partial"} else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": _safe_text(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))
        payload["go_no_go"]["combined_staging_gate"] = "Needs-Input"

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_staging_smoke"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "read_only": payload["read_only"],
        "execute_requested": execute,
        "real_llm_executed": payload["real_llm_executed"],
        "database_connected": payload["database_connected"],
        "redis_connected": payload["redis_connected"],
        "external_mcp_connected": payload["external_mcp_connected"],
        "migration_executed": payload["migration_executed"],
        "business_data_written": payload["business_data_written"],
        "audit_data_written": payload["audit_data_written"],
        "metrics_data_written": payload["metrics_data_written"],
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": _safe_text(output_root),
        "domain_count": len(domain_results),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成或执行 v4.4 受控真实集成 staging smoke 报告")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="请求真实 smoke；仍需 REAL_INTEGRATION_STAGING_SMOKE_ENABLED 和单域 opt-in")
    parser.add_argument(
        "--domains",
        default=",".join(DOMAIN_IDS),
        help="逗号分隔的 smoke 域，默认覆盖 real_llm,postgres,redis,external_mcp。",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    selected_domains = [item.strip() for item in str(args.domains or "").split(",") if item.strip()]
    summary = build_real_integration_staging_smoke(
        output_dir=args.output_dir,
        execute=args.execute,
        domains=selected_domains,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
