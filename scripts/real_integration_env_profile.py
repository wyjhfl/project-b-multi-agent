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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "real_integration_env_profile"
DEFAULT_DEV_TEMPLATE = ROOT_DIR / ".env.example"
DEFAULT_PROD_TEMPLATE = ROOT_DIR / ".env.production.example"

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
BOUNDARY_DECLARATIONS = [
    "只读生成 v4.4 real integration env profile 报告。",
    "只解析 .env.example 与 .env.production.example 的键名和值是否存在。",
    "不连接真实 LLM、PostgreSQL、Redis 或外部 MCP Server。",
    "不执行 Alembic migration，不写业务、审计或指标数据。",
    "对 secret-like 值仅记录 redacted 或 placeholder，不输出原文。",
    "REAL_LLM_API_KEY_ENV 只检查指向的目标环境变量是否存在，不读取目标值。",
    "缺少模板关键键或当前 opt-in 条件缺失时只能是 skipped 或 partial，不得伪造 success。",
]

SECRET_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret|database_url|redis_url)"
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*[^\s,<]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^@\s:]+:[^@\s]+@"),
]
PLACEHOLDER_PATTERNS = [
    re.compile(r"(?i)<replace"),
    re.compile(r"(?i)change-me"),
    re.compile(r"(?i)placeholder"),
    re.compile(r"(?i)example"),
]

DOMAIN_SPECS = [
    {
        "domain_id": "real_llm",
        "name": "真实 LLM env profile",
        "required_keys": [
            "REAL_LLM_PREFLIGHT_ENABLED",
            "REAL_LLM_ACCEPTANCE_ENABLED",
            "REAL_LLM_SMOKE_ENABLED",
            "REAL_LLM_MODEL",
            "REAL_LLM_API_KEY_ENV",
        ],
        "development_template_required_keys": [
            "REAL_LLM_PREFLIGHT_ENABLED",
            "REAL_LLM_ACCEPTANCE_ENABLED",
            "REAL_LLM_SMOKE_ENABLED",
            "REAL_LLM_MODEL",
            "REAL_LLM_API_KEY_ENV",
        ],
        "production_template_required_keys": [
            "REAL_LLM_PREFLIGHT_ENABLED",
            "REAL_LLM_ACCEPTANCE_ENABLED",
            "REAL_LLM_SMOKE_ENABLED",
            "REAL_LLM_PROVIDER",
            "REAL_LLM_MODEL",
            "REAL_LLM_BASE_URL",
            "REAL_LLM_API_KEY_ENV",
            "REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS",
            "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        ],
        "production_template_expected_state": "opt_in_disabled_by_default",
        "current_env_keys": [
            "REAL_LLM_PREFLIGHT_ENABLED",
            "REAL_LLM_ACCEPTANCE_ENABLED",
            "REAL_LLM_SMOKE_ENABLED",
            "REAL_LLM_MODEL",
            "REAL_LLM_API_KEY_ENV",
        ],
        "opt_in_conditions": [
            ("opt_in:REAL_LLM_PREFLIGHT_ENABLED", lambda: _env_enabled("REAL_LLM_PREFLIGHT_ENABLED")),
            ("opt_in:REAL_LLM_ACCEPTANCE_ENABLED", lambda: _env_enabled("REAL_LLM_ACCEPTANCE_ENABLED")),
            ("opt_in:REAL_LLM_SMOKE_ENABLED", lambda: _env_enabled("REAL_LLM_SMOKE_ENABLED")),
            ("env:REAL_LLM_MODEL", lambda: _env_present("REAL_LLM_MODEL")),
            ("env:REAL_LLM_API_KEY_ENV", lambda: _env_present("REAL_LLM_API_KEY_ENV")),
        ],
    },
    {
        "domain_id": "postgres",
        "name": "PostgreSQL env profile",
        "required_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
        "development_template_required_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
        "production_template_required_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
        "production_template_expected_state": "configured_placeholder_present",
        "current_env_keys": ["STORAGE_BACKEND", "DATABASE_URL"],
        "opt_in_conditions": [
            ("opt_in:STORAGE_BACKEND_postgres", lambda: _env_equals("STORAGE_BACKEND", "postgres")),
            ("env:DATABASE_URL", lambda: _env_present("DATABASE_URL")),
        ],
    },
    {
        "domain_id": "redis",
        "name": "Redis env profile",
        "required_keys": ["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_BACKEND"],
        "development_template_required_keys": ["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_BACKEND"],
        "production_template_required_keys": ["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_BACKEND"],
        "production_template_expected_state": "configured_placeholder_present",
        "current_env_keys": ["REDIS_ENABLED", "REDIS_URL", "RATE_LIMIT_BACKEND"],
        "opt_in_conditions": [
            ("opt_in:REDIS_ENABLED", lambda: _env_enabled("REDIS_ENABLED")),
            ("env:REDIS_URL", lambda: _env_present("REDIS_URL")),
            ("opt_in:RATE_LIMIT_BACKEND_redis", lambda: _env_equals("RATE_LIMIT_BACKEND", "redis")),
        ],
    },
    {
        "domain_id": "external_mcp",
        "name": "外部 MCP env profile",
        "required_keys": [
            "MCP_MODE",
            "MCP_SERVER_COMMAND",
            "MCP_SERVER_COMMAND_ALLOWLIST",
            "MCP_TOOL_ALLOWLIST",
            "MCP_SERVER_ENV_ALLOWLIST",
            "MCP_SERVER_TIMEOUT_SECONDS",
        ],
        "development_template_required_keys": [
            "MCP_MODE",
            "MCP_SERVER_COMMAND",
            "MCP_SERVER_COMMAND_ALLOWLIST",
            "MCP_TOOL_ALLOWLIST",
            "MCP_SERVER_ENV_ALLOWLIST",
            "MCP_SERVER_TIMEOUT_SECONDS",
        ],
        "production_template_required_keys": [
            "MCP_MODE",
            "MCP_SERVER_COMMAND",
            "MCP_SERVER_COMMAND_ALLOWLIST",
            "MCP_TOOL_ALLOWLIST",
            "MCP_SERVER_ENV_ALLOWLIST",
            "MCP_SERVER_TIMEOUT_SECONDS",
        ],
        "production_template_expected_state": "opt_in_disabled_by_default",
        "current_env_keys": [
            "MCP_MODE",
            "MCP_SERVER_COMMAND",
            "MCP_SERVER_COMMAND_ALLOWLIST",
            "MCP_TOOL_ALLOWLIST",
            "MCP_SERVER_ENV_ALLOWLIST",
            "MCP_SERVER_TIMEOUT_SECONDS",
        ],
        "opt_in_conditions": [
            ("opt_in:MCP_MODE_real", lambda: _env_equals("MCP_MODE", "real")),
            ("env:MCP_SERVER_COMMAND", lambda: _env_present("MCP_SERVER_COMMAND")),
            ("env:MCP_SERVER_COMMAND_ALLOWLIST", lambda: _env_present("MCP_SERVER_COMMAND_ALLOWLIST")),
            ("env:MCP_TOOL_ALLOWLIST", lambda: _env_present("MCP_TOOL_ALLOWLIST")),
        ],
    },
    {
        "domain_id": "staging_smoke",
        "name": "真实集成 staging smoke env profile",
        "required_keys": [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
            "REAL_LLM_STAGING_SMOKE_EXECUTE",
            "POSTGRES_STAGING_SMOKE_EXECUTE",
            "REDIS_STAGING_SMOKE_EXECUTE",
            "MCP_STAGING_SMOKE_EXECUTE",
        ],
        "development_template_required_keys": [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
            "REAL_LLM_STAGING_SMOKE_EXECUTE",
            "POSTGRES_STAGING_SMOKE_EXECUTE",
            "REDIS_STAGING_SMOKE_EXECUTE",
            "MCP_STAGING_SMOKE_EXECUTE",
        ],
        "production_template_required_keys": [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
            "REAL_LLM_STAGING_SMOKE_EXECUTE",
            "POSTGRES_STAGING_SMOKE_EXECUTE",
            "REDIS_STAGING_SMOKE_EXECUTE",
            "MCP_STAGING_SMOKE_EXECUTE",
        ],
        "production_template_expected_state": "opt_in_disabled_by_default",
        "current_env_keys": [
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
            "REAL_LLM_STAGING_SMOKE_EXECUTE",
            "POSTGRES_STAGING_SMOKE_EXECUTE",
            "REDIS_STAGING_SMOKE_EXECUTE",
            "MCP_STAGING_SMOKE_EXECUTE",
        ],
        "opt_in_conditions": [
            ("opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED", lambda: _env_enabled("REAL_INTEGRATION_STAGING_SMOKE_ENABLED")),
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


def _env_present(key: str) -> bool:
    return bool(os.getenv(key))


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_equals(key: str, expected: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() == expected.lower()


def _parse_env_file(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def _is_placeholder_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in PLACEHOLDER_PATTERNS)


def _is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_PATTERN.search(key))


def _contains_secret_like_plaintext(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, str):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    else:
        text = value
    if _is_placeholder_value(text):
        return False
    return any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS)


def _safe_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "[redacted-secret-like-text]" if _contains_secret_like_plaintext(text) else text


def _template_value_profile(key: str, value: str) -> tuple[dict[str, Any], bool]:
    is_secret_key = _is_secret_key(key)
    secret_like_plaintext = _contains_secret_like_plaintext(value)
    placeholder = bool(value) and _is_placeholder_value(value)
    blocked = secret_like_plaintext and not placeholder

    if not value:
        display_value = None
        value_state = "empty"
    elif key.endswith("_ENV") and not secret_like_plaintext:
        display_value = value
        value_state = "env_name"
    elif placeholder:
        display_value = "[placeholder]"
        value_state = "placeholder"
    elif is_secret_key or secret_like_plaintext:
        display_value = "[redacted-secret-like-value]"
        value_state = "redacted"
    else:
        display_value = "[literal]"
        value_state = "literal"

    return (
        {
            "value_present": bool(value),
            "value_state": value_state,
            "display_value": display_value,
            "secret_like_key": is_secret_key,
            "placeholder": placeholder,
        },
        blocked,
    )


def _template_profile(template_path: Path, required_keys: list[str], template_label: str) -> tuple[dict[str, Any], list[str], list[str]]:
    entries = _parse_env_file(template_path)
    key_profiles: dict[str, Any] = {}
    missing_keys: list[str] = []
    blocked_by: list[str] = []

    for key in required_keys:
        if key not in entries:
            missing_keys.append(f"template:{template_label}:{key}")
            continue

        profile, blocked = _template_value_profile(key, entries[key])
        key_profiles[key] = profile
        if blocked:
            blocked_by.append(f"template:{template_label}:{key}:secret_like_plaintext")

    return (
        {
            "template_path": _safe_text(template_path),
            "required_keys_present": len(missing_keys) == 0,
            "required_key_count": len(required_keys),
            "key_profiles": key_profiles,
            "missing_keys": missing_keys,
        },
        missing_keys,
        blocked_by,
    )


def _target_env_profile() -> tuple[dict[str, Any], list[str], list[str]]:
    blocked_by: list[str] = []
    missing_conditions: list[str] = []
    env_name = (os.getenv("REAL_LLM_API_KEY_ENV", "") or "").strip()
    safe_env_name = env_name if env_name and not _contains_secret_like_plaintext(env_name) else None

    if env_name and safe_env_name is None:
        blocked_by.append("env_target:REAL_LLM_API_KEY_ENV_secret_like_value")

    target_env_present = bool(safe_env_name and os.getenv(safe_env_name))
    if not target_env_present:
        missing_conditions.append("env_target:REAL_LLM_API_KEY_ENV")

    return (
        {
            "env_name_key": "REAL_LLM_API_KEY_ENV",
            "env_name_present": bool(env_name),
            "env_name": safe_env_name,
            "target_env_present": target_env_present,
        },
        missing_conditions,
        blocked_by,
    )


def _current_env_presence(keys: list[str]) -> dict[str, bool]:
    return {key: _env_present(key) for key in keys}


def _domain_profile(spec: dict[str, Any], dev_template_path: Path, prod_template_path: Path) -> dict[str, Any]:
    dev_template, dev_missing, dev_blocked = _template_profile(
        dev_template_path,
        spec["development_template_required_keys"],
        ".env.example",
    )
    prod_template, prod_missing, prod_blocked = _template_profile(
        prod_template_path,
        spec["production_template_required_keys"],
        ".env.production.example",
    )
    current_env = _current_env_presence(spec["current_env_keys"])
    opt_in_missing = [condition_id for condition_id, check in spec["opt_in_conditions"] if not check()]
    blocked_by = sorted(set(dev_blocked + prod_blocked))
    missing_conditions = sorted(set(dev_missing + prod_missing + opt_in_missing))

    target_env = None
    if spec["domain_id"] == "real_llm":
        target_env, target_missing, target_blocked = _target_env_profile()
        missing_conditions = sorted(set(missing_conditions + target_missing))
        blocked_by = sorted(set(blocked_by + target_blocked))

    status = "blocked" if blocked_by else ("partial" if not missing_conditions else "skipped")
    return {
        "domain_id": spec["domain_id"],
        "name": spec["name"],
        "status": status,
        "required_keys": spec["required_keys"],
        "development_template_expected_values": dev_template,
        "production_template_expected_status": {
            "domain_expected_state": spec["production_template_expected_state"],
            **prod_template,
        },
        "current_env_present": current_env,
        "target_env_present": target_env,
        "missing_conditions": missing_conditions,
        "blocked_by": blocked_by,
        "read_only": True,
    }


def _derive_status(profiles: list[dict[str, Any]]) -> str:
    statuses = [item["status"] for item in profiles]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if all(status == "partial" for status in statuses):
        return "partial"
    return "skipped"


def _execution_flags() -> dict[str, bool]:
    return {flag: False for flag in REQUIRED_FALSE_FLAGS}


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.4 real integration env profile（只读）",
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
        "## 域画像",
    ]
    for item in payload.get("profiles", []):
        lines.extend(
            [
                f"### {item.get('domain_id', '')}",
                f"- status: {item.get('status', '')}",
                f"- required_keys: {json.dumps(item.get('required_keys', []), ensure_ascii=False)}",
                f"- current_env_present: {json.dumps(item.get('current_env_present', {}), ensure_ascii=False)}",
                f"- target_env_present: {json.dumps(item.get('target_env_present', {}), ensure_ascii=False)}",
                f"- missing_conditions: {json.dumps(item.get('missing_conditions', []), ensure_ascii=False)}",
                f"- blocked_by: {json.dumps(item.get('blocked_by', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_real_integration_env_profile(
    *,
    output_dir: str | Path | None = None,
    development_template_path: str | Path | None = None,
    production_template_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    dev_template_path = Path(development_template_path) if development_template_path else DEFAULT_DEV_TEMPLATE
    prod_template_path = Path(production_template_path) if production_template_path else DEFAULT_PROD_TEMPLATE

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    profiles = [_domain_profile(spec, dev_template_path, prod_template_path) for spec in DOMAIN_SPECS]
    status = _derive_status(profiles)
    missing_conditions = sorted({item for profile in profiles for item in profile.get("missing_conditions", [])})
    blocked_by = sorted({item for profile in profiles for item in profile.get("blocked_by", [])})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.4.4",
        "phase": "v4.4 Phase 24.4 Env Profile Checker",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "profiles": profiles,
        "profile_count": len(profiles),
        "domain_count": len(profiles),
        "missing_conditions": missing_conditions,
        "blocked_by": blocked_by,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "secret_plaintext_output": False,
        "development_template_path": _safe_text(dev_template_path),
        "production_template_path": _safe_text(prod_template_path),
        "output_dir": _safe_text(output_root),
        **_execution_flags(),
    }

    if _contains_secret_like_plaintext(payload):
        payload["status"] = "blocked"
        payload["blocked_by"] = sorted(set(payload["blocked_by"] + ["output:secret_like_text_detected"]))
        payload["secret_plaintext_output"] = False

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_real_integration_env_profile"
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
        "profile_count": len(profiles),
        "missing_count": len(payload["missing_conditions"]),
        "blocked_count": len(payload["blocked_by"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.4 real integration env profile 只读报告（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--development-template-path", default=str(DEFAULT_DEV_TEMPLATE))
    parser.add_argument("--production-template-path", default=str(DEFAULT_PROD_TEMPLATE))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_real_integration_env_profile(
        output_dir=args.output_dir,
        development_template_path=args.development_template_path,
        production_template_path=args.production_template_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
