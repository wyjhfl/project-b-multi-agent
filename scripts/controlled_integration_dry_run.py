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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_integration_dry_run"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
READINESS_STATUS_VOCABULARY = ["ready", "skipped", "blocked", "partial"]

BOUNDARY_DECLARATIONS = [
    "只读受控集成 dry-run checklist",
    "仅检查环境变量存在性、本地文件存在性和可选 readiness JSON 安全元数据",
    "仅输出 env name 与 present true/false，不输出真实 secret 值",
    "不调用真实外网 LLM",
    "不连接真实外部 MCP",
    "不启动服务",
    "不默认启用 auth/RBAC/Redis/PostgreSQL",
    "不写业务数据",
    "缺少 opt-in 条件时保持 skipped，不伪造成 ready/success",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称真实 LLM 生产验收完成",
    "不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _env_present(keys: list[str]) -> dict[str, dict[str, bool]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _env_enabled(key: str) -> bool:
    value = os.getenv(key)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _missing_from_presence(presence: dict[str, dict[str, bool]]) -> list[str]:
    return [f"env:{key}" for key, item in presence.items() if not item.get("present", False)]


def _normalize_source_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "ready":
        return "ready"
    if raw in {"skipped", "blocked", "partial"}:
        return raw
    if raw == "success":
        return "ready"
    if raw == "failed":
        return "blocked"
    return "skipped"


def _load_readiness_report(path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": ["readiness_report:input_not_provided"],
            "integrations": {},
            "metadata": {},
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "provided": True,
            "path": str(path),
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": ["readiness_report:path_not_found"],
            "integrations": {},
            "metadata": {},
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "provided": True,
            "path": str(path),
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": ["readiness_report:json_file_required"],
            "integrations": {},
            "metadata": {},
            "warnings": [],
            "secret_detected": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "provided": True,
            "path": str(path),
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": ["readiness_report:json_parse_failed"],
            "integrations": {},
            "metadata": {},
            "warnings": [f"readiness_report:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "provided": True,
            "path": str(path),
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": ["readiness_report:json_empty_or_not_object"],
            "integrations": {},
            "metadata": {},
            "warnings": [],
            "secret_detected": False,
        }

    secret_detected = _contains_secret_like_text(json.dumps(payload, ensure_ascii=False))
    source_integrations: dict[str, dict[str, Any]] = {}
    for item in _safe_list(payload.get("integrations")):
        if not isinstance(item, dict):
            continue
        integration_id = str(item.get("integration_id") or "").strip()
        if not integration_id:
            continue
        missing = [_sanitize_text(value) for value in _safe_list(item.get("missing_conditions"))]
        skipped = [_sanitize_text(value) for value in _safe_list(item.get("skipped_reasons"))]
        source_integrations[integration_id] = {
            "readiness_status": _normalize_source_status(item.get("readiness_status") or item.get("status")),
            "missing_condition_count": len(missing),
            "skipped_reason_count": len(skipped),
            "missing_conditions": missing,
            "skipped_reasons": skipped,
            "read_only": bool(item.get("read_only", False)),
            "real_llm_executed": bool(item.get("real_llm_executed", False)),
        }

    status = _normalize_source_status(payload.get("readiness_status") or payload.get("status"))
    missing_conditions = [_sanitize_text(value) for value in _safe_list(payload.get("missing_conditions"))]
    skipped_reasons = [_sanitize_text(value) for value in _safe_list(payload.get("skipped_reasons"))]
    metadata = {
        "version": _sanitize_text(payload.get("version", "")),
        "mode": _sanitize_text(payload.get("mode", "")),
        "status": status,
        "read_only": bool(payload.get("read_only", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "integration_count": len(source_integrations),
        "missing_condition_count": len(missing_conditions),
        "skipped_reason_count": len(skipped_reasons),
    }
    if status == "skipped":
        missing_conditions.append("readiness_report:source_status_skipped")
    if metadata["real_llm_executed"]:
        missing_conditions.append("readiness_report:real_llm_executed_unexpected")
    if payload.get("read_only") is False:
        missing_conditions.append("readiness_report:not_read_only")
    if secret_detected:
        missing_conditions.append("readiness_report:secret_like_value_detected")

    return {
        "provided": True,
        "path": str(path),
        "exists": True,
        "loaded": True,
        "status": status,
        "missing_conditions": missing_conditions + skipped_reasons,
        "integrations": source_integrations,
        "metadata": metadata,
        "warnings": (
            [_sanitize_text(value) for value in _safe_list(payload.get("warnings"))]
            + (["readiness_report:secret_like_value_detected"] if secret_detected else [])
        ),
        "secret_detected": secret_detected,
    }


def _integration_definitions() -> list[dict[str, Any]]:
    return [
        {
            "integration_id": "real_llm",
            "name": "真实 LLM 受控 dry-run",
            "env_keys": [
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
                "REAL_LLM_MODEL",
                "REAL_LLM_API_KEY_ENV",
            ],
            "enabled_keys": [
                "REAL_LLM_SMOKE_ENABLED",
                "REAL_LLM_ACCEPTANCE_ENABLED",
                "REAL_LLM_PREFLIGHT_ENABLED",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
            ],
            "local_checks": {"real_llm_smoke_script": "scripts/real_llm_smoke.ps1"},
            "recommended_actions": ["缺少真实 LLM opt-in 条件时保持 skipped，不执行真实外网 LLM。"],
        },
        {
            "integration_id": "oidc",
            "name": "OIDC 最小接入 dry-run",
            "env_keys": ["OIDC_ENABLED", "OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET_ENV", "OIDC_REDIRECT_URI"],
            "enabled_keys": ["OIDC_ENABLED"],
            "local_checks": {"oidc_drill_doc": "docs/oidc_minimal_idp_drill_v31.md"},
            "recommended_actions": ["仅验证 OIDC 配置存在性，不宣称生产级 SSO/OIDC 完成。"],
        },
        {
            "integration_id": "external_mcp",
            "name": "外部 MCP dry-run",
            "env_keys": ["MCP_MODE", "MCP_SERVER_COMMAND", "MCP_TOOL_ALLOWLIST"],
            "expected_values": {"MCP_MODE": "real"},
            "local_checks": {"stdio_client": "app/tools/mcp/stdio_client.py", "fake_stdio_fixture": "tests/fixtures/fake_mcp_stdio_server.py"},
            "recommended_actions": ["真实 MCP 需显式 command 与 allowlist；默认继续使用 fake/offline。"],
        },
        {
            "integration_id": "postgres",
            "name": "PostgreSQL dry-run",
            "env_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
            "expected_values": {"STORAGE_BACKEND": "postgres"},
            "local_checks": {"prod_compose": "docker-compose.prod.yml", "alembic_ini": "alembic.ini"},
            "recommended_actions": ["默认 storage_backend=sqlite；启用 PostgreSQL 前先运行部署门禁与迁移预检。"],
        },
        {
            "integration_id": "redis",
            "name": "Redis dry-run",
            "env_keys": ["REDIS_ENABLED", "REDIS_URL"],
            "enabled_keys": ["REDIS_ENABLED"],
            "local_checks": {"compose": "docker-compose.yml"},
            "recommended_actions": ["默认 REDIS_ENABLED=false；多实例限流再接入 Redis 或网关级限流。"],
        },
        {
            "integration_id": "frontend_build_network",
            "name": "前端 build/network dependency dry-run",
            "env_keys": ["NEXT_PUBLIC_API_BASE_URL"],
            "local_checks": {"package_lock": "frontend/package-lock.json", "next_config": "frontend/next.config.ts"},
            "recommended_actions": ["前端 build 依赖仅做本地可验证检查，不触发网络安装或服务启动。"],
        },
        {
            "integration_id": "deployment_guard",
            "name": "Deployment guard dry-run",
            "env_keys": ["APP_ENV", "AUTH_ENABLED", "RBAC_ENABLED", "JWT_SECRET", "DATABASE_URL", "REDIS_URL"],
            "local_checks": {"deployment_guard": "app/core/deployment_guard.py", "deployment_api": "app/api/deployment.py"},
            "recommended_actions": ["生产门禁应返回结构化结果；dry-run 不默认启用 auth/RBAC/Redis/PostgreSQL。"],
        },
        {
            "integration_id": "audit_export_redaction",
            "name": "Audit export/redaction dry-run",
            "env_keys": [],
            "local_checks": {"audit_api": "app/api/audit.py", "structured_logging": "app/core/structured_logging.py"},
            "recommended_actions": ["复核审计导出脱敏边界，不导出 prompt 原文、密钥原文或连接串密码原文。"],
        },
    ]


def _evaluate_definition(definition: dict[str, Any], readiness_report: dict[str, Any]) -> dict[str, Any]:
    integration_id = str(definition["integration_id"])
    env_keys = list(definition.get("env_keys", []))
    env_presence = _env_present(env_keys)
    local_checks = {
        key: {"path": path, "present": _path_exists(path)}
        for key, path in dict(definition.get("local_checks", {})).items()
    }
    missing_conditions = _missing_from_presence(env_presence)
    missing_conditions.extend(f"local:{key}" for key, item in local_checks.items() if not item["present"])

    for key in definition.get("enabled_keys", []):
        if not _env_enabled(key):
            missing_conditions.append(f"opt_in:{key}_not_enabled")

    for key, expected in dict(definition.get("expected_values", {})).items():
        current = os.getenv(key)
        if current is None:
            continue
        if str(current).strip().lower() != str(expected).strip().lower():
            missing_conditions.append(f"opt_in:{key}_not_{expected}")

    source = dict(readiness_report.get("integrations", {}).get(integration_id, {}))
    source_status = _normalize_source_status(source.get("readiness_status")) if source else "skipped"
    source_missing = [_sanitize_text(value) for value in _safe_list(source.get("missing_conditions"))]
    source_skipped = [_sanitize_text(value) for value in _safe_list(source.get("skipped_reasons"))]
    if readiness_report.get("loaded") and not source:
        missing_conditions.append(f"readiness_report:{integration_id}_not_found")
    if source_status == "skipped":
        if source:
            missing_conditions.append(f"readiness_report:{integration_id}_source_status_skipped")
        missing_conditions.extend(source_missing + source_skipped)
    if source_status == "blocked":
        missing_conditions.append(f"readiness_report:{integration_id}_blocked")

    if source.get("real_llm_executed"):
        missing_conditions.append(f"readiness_report:{integration_id}_real_llm_executed_unexpected")
    if source and source.get("read_only") is False:
        missing_conditions.append(f"readiness_report:{integration_id}_not_read_only")

    readiness_status = _derive_integration_status(
        local_missing=missing_conditions,
        source_status=source_status,
        readiness_report_loaded=bool(readiness_report.get("loaded")),
    )
    skipped_reasons = missing_conditions if readiness_status == "skipped" else []
    return {
        "integration_id": integration_id,
        "name": str(definition["name"]),
        "readiness_status": readiness_status,
        "env": env_presence,
        "local_checks": local_checks,
        "source_readiness": {
            "provided": bool(readiness_report.get("provided")),
            "loaded": bool(readiness_report.get("loaded")),
            "readiness_status": source_status,
            "missing_condition_count": int(source.get("missing_condition_count", 0)),
            "skipped_reason_count": int(source.get("skipped_reason_count", 0)),
        },
        "missing_conditions": sorted(set(missing_conditions)),
        "skipped_reasons": sorted(set(skipped_reasons)),
        "recommended_actions": list(definition.get("recommended_actions", [])),
        "read_only": True,
        "real_llm_executed": False,
    }


def _derive_integration_status(*, local_missing: list[str], source_status: str, readiness_report_loaded: bool) -> str:
    if any("_real_llm_executed_unexpected" in item or "_not_read_only" in item for item in local_missing):
        return "blocked"
    if "blocked" == source_status:
        return "blocked"
    if not local_missing and (not readiness_report_loaded or source_status == "ready"):
        return "ready"
    if source_status == "partial":
        return "partial"
    if readiness_report_loaded and source_status == "ready" and local_missing:
        return "partial"
    return "skipped"


def _derive_status(integrations: list[dict[str, Any]]) -> str:
    statuses = [str(item.get("readiness_status", "")) for item in integrations]
    if "blocked" in statuses:
        return "blocked"
    if all(status == "ready" for status in statuses):
        return "success"
    if any(status in {"ready", "partial"} for status in statuses):
        return "partial"
    return "skipped"


def _recommended_actions(status: str, integrations: list[dict[str, Any]], readiness_report: dict[str, Any]) -> list[str]:
    actions = [
        "保持默认 fake/offline 路径；未显式 opt-in 时不要执行真实外网 LLM。",
        "dry-run 结果仅用于安排人工受控演练，不自动改变 Go/No-Go 结论。",
        "只输出环境变量名称和 present 状态，后续人工复核时也不要粘贴 secret 原文。",
    ]
    if not readiness_report.get("loaded"):
        actions.append("如需串联 Phase 14.4 证据，可通过 --readiness-report 传入 optional integration readiness JSON。")
    if status == "skipped":
        actions.append("补齐必要 opt-in 条件或本地文件后重新生成 dry-run checklist。")
    if status == "blocked":
        actions.append("先处理 not_read_only 或 unexpected real LLM execution 等阻断项，再安排受控演练。")
    for item in integrations:
        actions.extend(str(action) for action in item.get("recommended_actions", []))
    return sorted(set(actions))


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.5 受控集成 dry-run checklist（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- status: {payload.get('status', '')}",
        f"- read_only: {payload.get('read_only', True)}",
        f"- real_llm_executed: {payload.get('real_llm_executed', False)}",
        "",
        "## 集成项",
    ]
    for item in payload.get("integrations", []):
        lines.extend(
            [
                f"### {item.get('name', '')}",
                f"- integration_id: {item.get('integration_id', '')}",
                f"- readiness_status: {item.get('readiness_status', '')}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                f"- skipped_reasons: {json.dumps(item.get('skipped_reasons', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 建议动作")
    for item in payload.get("recommended_actions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_controlled_integration_dry_run(
    *,
    output_dir: str | Path | None = None,
    readiness_report: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    readiness = _load_readiness_report(readiness_report)
    integrations = [_evaluate_definition(definition, readiness) for definition in _integration_definitions()]
    status = _derive_status(integrations)
    if readiness.get("secret_detected"):
        status = "blocked"
    missing_conditions = sorted(
        {
            item
            for integration in integrations
            for item in integration.get("missing_conditions", [])
        }
        | set(readiness.get("missing_conditions", []))
    )
    skipped_reasons = sorted(
        {
            item
            for integration in integrations
            for item in integration.get("skipped_reasons", [])
        }
    )
    warnings = sorted(set(readiness.get("warnings", [])))

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.5.0",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "readiness_status_vocabulary": READINESS_STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "service_started": False,
        "default_auth_enabled": False,
        "default_rbac_enabled": False,
        "default_postgres_enabled": False,
        "default_redis_enabled": False,
        "input_sources": {
            "readiness_report": _sanitize_text(readiness_report) if readiness_report else None,
        },
        "readiness_report": {
            "provided": bool(readiness.get("provided")),
            "exists": bool(readiness.get("exists")),
            "loaded": bool(readiness.get("loaded")),
            "status": readiness.get("status", "skipped"),
            "metadata": readiness.get("metadata", {}),
        },
        "integrations": integrations,
        "env_presence": {
            item["integration_id"]: item.get("env", {})
            for item in integrations
        },
        "missing_conditions": missing_conditions,
        "skipped_reasons": skipped_reasons,
        "warnings": warnings,
        "recommended_actions": _recommended_actions(status, integrations, readiness),
        "go_no_go_hint": _go_no_go_hint(status),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_integration_dry_run"
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
        "external_mcp_connected": False,
        "service_started": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "integration_count": len(integrations),
        "missing_conditions": missing_conditions,
    }


def _go_no_go_hint(status: str) -> str:
    if status == "blocked":
        return "No-Go：存在需要人工关闭的阻断项，尤其需复核 secret、只读边界或真实外部执行风险。"
    if status == "failed":
        return "No-Go：输出不可用或结果无法解释。"
    if status == "partial":
        return "继续观察或补证：部分集成项可解释，缺失项必须保留 skipped/partial 语义。"
    if status == "skipped":
        return "继续观察或补证：缺少 opt-in 或输入证据，本轮不进入真实集成验收。"
    return "企业内网受控试点可继续，但不代表真实生产验收完成。"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.5 受控集成 dry-run 只读 checklist（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--readiness-report", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_controlled_integration_dry_run(
        output_dir=args.output_dir,
        readiness_report=args.readiness_report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
