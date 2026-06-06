from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_production_environment_checklist"
PLAN_PATH = ROOT_DIR / "docs" / "v4_5_real_production_environment_landing_plan.md"

SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres"
SAFE_REDIS_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis"
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}

EVIDENCE_DIRS = {
    "env_profile": ROOT_DIR / "docs" / "reports" / "real_integration_env_profile",
    "xiaomi_llm_preflight": ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
    "staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "staging_gate": ROOT_DIR / "docs" / "reports" / "real_integration_staging_gate",
    "gap_register": ROOT_DIR / "docs" / "reports" / "real_integration_gap_register",
    "business_read_smoke": ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
}

DOMAIN_CHECKLIST = [
    {
        "domain_id": "real_llm",
        "owner": "LLM 集成负责人",
        "phase": "Phase 25.2",
        "environment": "L1 staging -> L2 生产试点",
        "required_config": [
            "REAL_LLM_ACCEPTANCE_ENABLED=true",
            "REAL_LLM_PREFLIGHT_ENABLED=true",
            "REAL_LLM_SMOKE_ENABLED=true",
            "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
            "REAL_LLM_PROVIDER=litellm",
            "REAL_LLM_MODEL=<approved-model>",
            "REAL_LLM_API_KEY_ENV=<external-secret-env-name>",
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
        ],
        "smoke_command": SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        "required_evidence": [
            "LLM preflight 网络检查通过",
            "token/cost/budget/cache/fallback 证据完整",
            "prompt、PII、API key 未进入日志、报告或审计导出",
        ],
        "no_go": ["无预算上限", "无 fallback", "输出 prompt 原文或 key 原文", "默认测试路径依赖真实 LLM"],
    },
    {
        "domain_id": "postgres",
        "owner": "数据库负责人",
        "phase": "Phase 25.3",
        "environment": "L1 staging -> L2 生产试点",
        "required_config": [
            "STORAGE_BACKEND=postgres",
            "DATABASE_URL=<external-secret-managed-url>",
            "Alembic migration 仅在人工批准窗口执行",
        ],
        "smoke_command": SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        "required_evidence": [
            "database_connected=true 的脱敏 smoke 报告",
            "migration 版本、执行窗口、回滚点记录",
            "Store Factory 主链路验证",
            "SQLite fallback 测试仍通过",
        ],
        "no_go": ["未经审批执行 migration", "默认开发路径被强制切到 PostgreSQL", "报告中出现 DATABASE_URL 原文"],
    },
    {
        "domain_id": "redis",
        "owner": "缓存/限流负责人",
        "phase": "Phase 25.4",
        "environment": "L1 staging -> L2 生产试点",
        "required_config": [
            "REDIS_ENABLED=true",
            "REDIS_URL=<external-secret-managed-url>",
            "RATE_LIMIT_BACKEND=redis",
        ],
        "smoke_command": SAFE_REDIS_INFRA_SMOKE_COMMAND,
        "required_evidence": [
            "redis_connected=true 的脱敏 smoke 报告",
            "Redis fixed-window 计数证据",
            "断连降级、恢复、告警证据",
            "多实例限流证据",
        ],
        "no_go": ["使用 memory backend 宣称多实例生产限流完成", "报告中出现 REDIS_URL 原文", "Redis 异常导致 500"],
    },
    {
        "domain_id": "external_mcp",
        "owner": "MCP 集成负责人",
        "phase": "Phase 25.5",
        "environment": "L1 staging -> L2 生产试点",
        "required_config": [
            "MCP_MODE=real",
            "MCP_SERVER_COMMAND=<approved-command>",
            "MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>",
            "MCP_TOOL_ALLOWLIST=<approved-tools>",
            "MCP_SERVER_ENV_ALLOWLIST=<approved-env-names>",
            "MCP_SERVER_TIMEOUT_SECONDS=<bounded-timeout>",
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
            "MCP_STAGING_SMOKE_EXECUTE=true",
        ],
        "smoke_command": SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
        "required_evidence": [
            "tools/list 成功的脱敏 smoke 报告",
            "ToolGateway discovery/call 二次 allowlist 证据",
            "PolicyEngine、Approval、Audit 链路证据",
            "MCP 进程生命周期和失败恢复证据",
        ],
        "no_go": [
            "MCP 工具绕过 ToolGateway、PolicyEngine、审批或审计",
            "command/tool allowlist 为空",
            "输出 MCP command 中的 secret 参数",
        ],
    },
    {
        "domain_id": "business_system",
        "owner": "业务系统集成负责人",
        "phase": "Phase 25.8",
        "environment": "L1 staging -> L2 生产试点",
        "required_config": [
            "BUSINESS_INTEGRATION_ENABLED=true",
            "BUSINESS_INTEGRATION_READ_ONLY=true",
            "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
            "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
            "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
            "BUSINESS_SYSTEM_BASE_URL_ENV=<external-secret-env-name>",
            "BUSINESS_SYSTEM_TOKEN_ENV=<external-secret-env-name>",
            "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
            "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
        ],
        "smoke_command": SAFE_BUSINESS_READ_SMOKE_COMMAND,
        "required_evidence": [
            "真实业务系统只读 probe 成功的脱敏 smoke 报告",
            "local_business_mock_used=false",
            "business_read_executed=true",
            "business_write_executed=false 且 business_data_written=false",
            "ToolGateway、PolicyEngine、allowlist、审计边界复核",
        ],
        "no_go": [
            "使用本地 mock 证据宣称真实业务系统验收完成",
            "执行真实业务写入或绕过审批/审计",
            "报告中出现业务系统 URL、token 或 Authorization 原文",
        ],
    },
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like_text(value: Any) -> bool:
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
                candidate = str(match.group(2) or "").strip().strip(" \"'<>[]{}\\")
                if candidate.lower() in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _safe_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "[redacted-secret-like-text]" if _contains_secret_like_text(text) else text


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob("*.json") if item.is_file()]
    if not files:
        return None
    return max(files, key=_json_report_sort_key)


def _iter_json_reports(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        (item for item in directory.glob("*.json") if item.is_file()),
        key=_json_report_sort_key,
        reverse=True,
    )


def _aggregate_safe_staging_smoke(directory: Path, current_payload: dict[str, Any]) -> dict[str, Any]:
    current_aggregated = (
        current_payload.get("aggregated_infra_flags")
        if isinstance(current_payload.get("aggregated_infra_flags"), dict)
        else {}
    )
    current_paths = (
        current_payload.get("aggregated_evidence_paths")
        if isinstance(current_payload.get("aggregated_evidence_paths"), dict)
        else {}
    )
    aggregated_flags = {
        "database_connected": bool(
            current_payload.get("database_connected") is True or current_aggregated.get("database_connected") is True
        ),
        "redis_connected": bool(
            current_payload.get("redis_connected") is True or current_aggregated.get("redis_connected") is True
        ),
        "external_mcp_connected": bool(
            current_payload.get("external_mcp_connected") is True
            or current_aggregated.get("external_mcp_connected") is True
        ),
    }
    evidence_paths: dict[str, str] = {
        str(key): _safe_text(value) or ""
        for key, value in current_paths.items()
    }
    secret_report_count = int(current_payload.get("aggregated_secret_report_count") or 0)
    unsafe_report_count = int(current_payload.get("aggregated_unsafe_report_count") or 0)
    safe_report_count = int(current_payload.get("aggregated_safe_report_count") or 0)
    for item in _iter_json_reports(directory):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _contains_secret_like_text(payload):
            secret_report_count += 1
            continue
        if payload.get("migration_executed") is True or payload.get("business_data_written") is True:
            unsafe_report_count += 1
            continue
        if payload.get("status") not in {"success", "partial"} or payload.get("secret_plaintext_output") is not False:
            continue
        safe_report_count += 1
        for flag in ("database_connected", "redis_connected", "external_mcp_connected"):
            if payload.get(flag) is True:
                aggregated_flags[flag] = True
                evidence_paths.setdefault(flag, _safe_text(item) or "")
    return {
        "aggregated_infra_flags": aggregated_flags,
        "aggregated_evidence_paths": evidence_paths,
        "aggregated_safe_report_count": safe_report_count,
        "aggregated_secret_report_count": secret_report_count,
        "aggregated_unsafe_report_count": unsafe_report_count,
    }


def _load_latest_evidence(evidence_id: str, directory: Path) -> dict[str, Any]:
    latest = _latest_json(directory)
    if latest is None:
        return {
            "evidence_id": evidence_id,
            "status": "skipped",
            "latest_json_path": None,
            "present": False,
            "missing_conditions": [f"evidence:{evidence_id}:missing"],
            "secret_detected": False,
            "safe_summary": {},
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "evidence_id": evidence_id,
            "status": "blocked",
            "latest_json_path": _safe_text(latest),
            "present": True,
            "missing_conditions": [f"evidence:{evidence_id}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
            "safe_summary": {},
        }

    secret_detected = _contains_secret_like_text(payload)
    status = str(payload.get("status") or "skipped")
    missing = payload.get("missing_conditions", [])
    if not isinstance(missing, list):
        missing = []
    if secret_detected:
        status = "blocked"
        missing = [*missing, f"evidence:{evidence_id}:secret_like_text_detected"]
    aggregate = _aggregate_safe_staging_smoke(directory, payload) if evidence_id == "staging_smoke" else {}
    aggregated_flags = (
        aggregate.get("aggregated_infra_flags")
        if isinstance(aggregate.get("aggregated_infra_flags"), dict)
        else payload.get("aggregated_infra_flags")
        if isinstance(payload.get("aggregated_infra_flags"), dict)
        else {}
    )
    aggregated_paths = (
        aggregate.get("aggregated_evidence_paths")
        if isinstance(aggregate.get("aggregated_evidence_paths"), dict)
        else payload.get("aggregated_evidence_paths")
        if isinstance(payload.get("aggregated_evidence_paths"), dict)
        else {}
    )
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    return {
        "evidence_id": evidence_id,
        "status": status if status in STATUS_VOCABULARY else "skipped",
        "latest_json_path": _safe_text(latest),
        "present": True,
        "missing_conditions": sorted({str(item) for item in missing}),
        "secret_detected": secret_detected,
        "safe_summary": {
            "generated_at": payload.get("generated_at"),
            "version": payload.get("version"),
            "phase": payload.get("phase"),
            "status": payload.get("status"),
            "profile_count": payload.get("profile_count"),
            "domain_count": payload.get("domain_count"),
            "evidence_count": payload.get("evidence_count"),
            "gap_count": payload.get("gap_count"),
            "api_key_present": payload.get("api_key_present"),
            "real_llm_executed": payload.get("real_llm_executed"),
            "network_check_executed": preflight.get("network_check_executed"),
            "network_check_allowed": preflight.get("network_check_allowed"),
            "acceptance_blockers": [
                str(item)
                for item in (
                    payload.get("acceptance_blockers")
                    if isinstance(payload.get("acceptance_blockers"), list)
                    else []
                )
            ],
            "database_connected": payload.get("database_connected"),
            "redis_connected": payload.get("redis_connected"),
            "external_mcp_connected": payload.get("external_mcp_connected"),
            "business_system_connected": payload.get("business_system_connected"),
            "business_read_executed": payload.get("business_read_executed"),
            "business_write_executed": payload.get("business_write_executed"),
            "business_data_written": payload.get("business_data_written"),
            "local_business_mock_used": payload.get("local_business_mock_used"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "aggregated_infra_flags": aggregated_flags,
            "aggregated_evidence_paths": {
                str(key): _safe_text(value)
                for key, value in aggregated_paths.items()
            },
            "aggregated_safe_report_count": aggregate.get("aggregated_safe_report_count", payload.get("aggregated_safe_report_count")),
            "aggregated_secret_report_count": aggregate.get("aggregated_secret_report_count", payload.get("aggregated_secret_report_count")),
            "aggregated_unsafe_report_count": aggregate.get("aggregated_unsafe_report_count", payload.get("aggregated_unsafe_report_count")),
        },
    }


def _business_system_missing_conditions(evidence: dict[str, dict[str, Any]]) -> list[str]:
    business = evidence.get("business_read_smoke", {})
    summary = business.get("safe_summary") if isinstance(business.get("safe_summary"), dict) else {}
    missing = [str(item) for item in business.get("missing_conditions", []) if str(item)]
    if business.get("status") == "skipped":
        missing.append("business_read_smoke:report_missing_or_skipped")
    if business.get("present") is not True:
        missing.append("business_read_smoke:report_not_found")
    if summary.get("local_business_mock_used") is True:
        missing.append("business_system:real_read_smoke_not_executed")
    if summary.get("business_read_executed") is not True:
        missing.append("business_system:read_not_executed")
    if summary.get("business_write_executed") is True:
        missing.append("business_system:write_executed")
    if summary.get("business_data_written") is True:
        missing.append("business_system:data_written")
    if summary.get("secret_plaintext_output") is True:
        missing.append("business_system:secret_plaintext_output")
    return sorted(set(missing))


def _real_integration_missing_conditions(domain_id: str, evidence: dict[str, dict[str, Any]]) -> list[str]:
    staging_smoke = evidence.get("staging_smoke", {})
    summary = staging_smoke.get("safe_summary") if isinstance(staging_smoke.get("safe_summary"), dict) else {}
    xiaomi_preflight = evidence.get("xiaomi_llm_preflight", {})
    xiaomi_summary = (
        xiaomi_preflight.get("safe_summary")
        if isinstance(xiaomi_preflight.get("safe_summary"), dict)
        else {}
    )
    aggregated_flags = (
        summary.get("aggregated_infra_flags")
        if isinstance(summary.get("aggregated_infra_flags"), dict)
        else {}
    )
    flag_by_domain = {
        "real_llm": ("real_llm_executed", "real_llm:not_executed"),
        "postgres": ("database_connected", "postgres:database_not_connected"),
        "redis": ("redis_connected", "redis:not_connected"),
        "external_mcp": ("external_mcp_connected", "external_mcp:not_connected"),
    }
    missing: list[str] = []
    flag_name, missing_id = flag_by_domain[domain_id]
    xiaomi_llm_proven = bool(
        domain_id == "real_llm"
        and xiaomi_preflight.get("present") is True
        and xiaomi_preflight.get("status") == "success"
        and xiaomi_preflight.get("secret_detected") is not True
        and xiaomi_summary.get("real_llm_executed") is True
        and xiaomi_summary.get("network_check_executed") is True
        and xiaomi_summary.get("secret_plaintext_output") is False
        and not xiaomi_summary.get("acceptance_blockers")
    )
    aggregated_proven = bool(aggregated_flags.get(flag_name) is True or xiaomi_llm_proven)
    if staging_smoke.get("status") == "skipped" and not aggregated_proven:
        missing.append("staging_smoke:report_missing_or_skipped")
    if staging_smoke.get("present") is not True and not aggregated_proven:
        missing.append("staging_smoke:report_not_found")
    if summary.get(flag_name) is not True and not aggregated_proven:
        missing.append(missing_id)
    if summary.get("secret_plaintext_output") is True:
        missing.append("staging_smoke:secret_plaintext_output")
    if domain_id == "real_llm":
        if xiaomi_preflight.get("secret_detected") is True:
            missing.append("xiaomi_llm_preflight:secret_like_text_detected")
        if xiaomi_preflight.get("present") is True and xiaomi_preflight.get("status") == "blocked":
            missing.append("xiaomi_llm_preflight:blocked")
    return sorted(set(missing))


def _build_domain_items(evidence: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    gap_status = evidence.get("gap_register", {}).get("status", "skipped")
    staging_gate_status = evidence.get("staging_gate", {}).get("status", "skipped")
    items: list[dict[str, Any]] = []
    for spec in DOMAIN_CHECKLIST:
        missing_conditions = []
        if spec["domain_id"] == "business_system":
            missing_conditions.extend(_business_system_missing_conditions(evidence))
        else:
            missing_conditions.extend(_real_integration_missing_conditions(str(spec["domain_id"]), evidence))
            if gap_status == "skipped":
                missing_conditions.append("gap_register:open_gaps_present")
        if spec["domain_id"] != "business_system" and staging_gate_status == "skipped":
            missing_conditions.append("staging_gate:source_status_skipped")
        domain_status = "partial"
        if not missing_conditions:
            domain_status = "partial"
        items.append(
            {
                **spec,
                "status": domain_status,
                "missing_conditions": missing_conditions,
                "manual_signoff_required": True,
                "production_direct_launch": "No-Go",
            }
        )
    return items


def _derive_status(evidence: dict[str, dict[str, Any]], domains: list[dict[str, Any]]) -> str:
    if any(item.get("secret_detected") for item in evidence.values()):
        return "blocked"
    if any(item["status"] == "blocked" for item in evidence.values()):
        return "blocked"
    if not any(item.get("present") for item in evidence.values()):
        return "skipped"
    if any(item["status"] == "skipped" for item in domains):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.5 真实生产环境落地 Checklist",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        f"- domain_count: {payload.get('domain_count', 0)}",
        "",
        "## 真实域",
    ]
    for item in payload.get("domains", []):
        lines.extend(
            [
                f"### {item.get('domain_id', '')}",
                f"- owner: {item.get('owner', '')}",
                f"- phase: {item.get('phase', '')}",
                f"- status: {item.get('status', '')}",
                f"- smoke_command: `{item.get('smoke_command', '')}`",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## No-Go")
    for item in payload.get("global_no_go", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_production_environment_checklist(
    *,
    output_dir: str | Path | None = None,
    evidence_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    effective_dirs = {key: Path(value) for key, value in (evidence_dirs or EVIDENCE_DIRS).items()}
    evidence = {evidence_id: _load_latest_evidence(evidence_id, directory) for evidence_id, directory in effective_dirs.items()}
    domains = _build_domain_items(evidence)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    status = _derive_status(evidence, domains)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.0",
        "phase": "v4.5 Real Production Environment Landing Checklist",
        "mode": "planning_and_evidence_check",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "plan_path": _safe_text(PLAN_PATH),
        "evidence": evidence,
        "domains": domains,
        "domain_count": len(domains),
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "production_pilot": "Needs-Input" if status in {"skipped", "blocked"} else "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "global_no_go": [
            "任一真实域仍无脱敏证据",
            "任一报告出现 secret-like 原文",
            "migration、真实工具调用或真实 LLM 调用绕过人工批准",
            "默认 fake/offline 路径被破坏",
            "public_production_direct_launch 被改成 Go",
        ],
        "output_dir": _safe_text(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["go_no_go"]["production_pilot"] = "Needs-Input"

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_production_environment_checklist"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

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
        "markdown_path": str(markdown_path),
        "output_dir": _safe_text(output_root),
        "domain_count": len(domains),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.5 真实生产环境落地 checklist（JSON + Markdown，只读）。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--evidence-root", default=str(ROOT_DIR / "docs" / "reports"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_root = Path(args.evidence_root)
    summary = build_real_production_environment_checklist(
        output_dir=args.output_dir,
        evidence_dirs={
            "env_profile": evidence_root / "real_integration_env_profile",
            "xiaomi_llm_preflight": evidence_root / "production_landing_xiaomi_llm_preflight",
            "staging_smoke": evidence_root / "real_integration_staging_smoke",
            "staging_gate": evidence_root / "real_integration_staging_gate",
            "gap_register": evidence_root / "real_integration_gap_register",
            "business_read_smoke": evidence_root / "business_system_read_smoke",
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
