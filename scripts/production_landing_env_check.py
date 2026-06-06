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
DEFAULT_ENV_PATH = ROOT_DIR / "local" / "production_landing.staging.env"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_env_check"
XIAOMI_PREFLIGHT_REPORT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight"

SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_XIAOMI_LLM_RESUME_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_landing_resume.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres"
SAFE_REDIS_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis"
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)
SAFE_INFRA_AND_LLM_SMOKE_COMMAND = " ; ".join(
    [
        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        SAFE_REDIS_INFRA_SMOKE_COMMAND,
        SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
    ]
)

REQUIRED_ENV_BY_DOMAIN = {
    "real_llm": [
        "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
        "REAL_LLM_STAGING_SMOKE_EXECUTE",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_PROVIDER",
        "REAL_LLM_MODEL",
        "REAL_LLM_BASE_URL",
        "REAL_LLM_API_KEY_ENV",
    ],
    "postgres": [
        "POSTGRES_STAGING_SMOKE_EXECUTE",
        "STORAGE_BACKEND",
        "DATABASE_URL",
    ],
    "redis": [
        "REDIS_STAGING_SMOKE_EXECUTE",
        "REDIS_ENABLED",
        "REDIS_URL",
        "RATE_LIMIT_BACKEND",
    ],
    "external_mcp": [
        "MCP_STAGING_SMOKE_EXECUTE",
        "MCP_MODE",
        "MCP_SERVER_COMMAND",
        "MCP_SERVER_COMMAND_ALLOWLIST",
        "MCP_TOOL_ALLOWLIST",
    ],
    "business_system": [
        "BUSINESS_INTEGRATION_ENABLED",
        "BUSINESS_INTEGRATION_READ_ONLY",
        "BUSINESS_INTEGRATION_WRITE_ENABLED",
        "BUSINESS_SYSTEM_BASE_URL_ENV",
        "BUSINESS_SYSTEM_TOKEN_ENV",
        "BUSINESS_SYSTEM_BASE_URL",
        "BUSINESS_SYSTEM_TOKEN",
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
        "BUSINESS_SYSTEM_BUSINESS_OWNER",
        "BUSINESS_SYSTEM_SECURITY_REVIEWER",
        "BUSINESS_SYSTEM_OPERATIONS_OWNER",
        "BUSINESS_SYSTEM_DATA_OWNER",
    ],
}

COMMAND_AFTER_FILL_BY_DOMAIN = {
    "real_llm": SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
    "postgres": SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
    "redis": SAFE_REDIS_INFRA_SMOKE_COMMAND,
    "external_mcp": SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
    "business_system": SAFE_BUSINESS_READ_SMOKE_COMMAND,
}

EXPECTED_VALUES = {
    "REAL_INTEGRATION_STAGING_SMOKE_ENABLED": "true",
    "REAL_LLM_STAGING_SMOKE_EXECUTE": "true",
    "REAL_LLM_ACCEPTANCE_ENABLED": "true",
    "REAL_LLM_PREFLIGHT_ENABLED": "true",
    "REAL_LLM_SMOKE_ENABLED": "true",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK": "true",
    "REAL_LLM_PROVIDER": "litellm",
    "REAL_LLM_MODEL": "mimo-v2.5-pro",
    "REAL_LLM_BASE_URL": "https://token-plan-cn.xiaomimimo.com/v1",
    "REAL_LLM_API_KEY_ENV": "XIAOMI_LLM_API_KEY",
    "POSTGRES_STAGING_SMOKE_EXECUTE": "true",
    "STORAGE_BACKEND": "postgres",
    "REDIS_STAGING_SMOKE_EXECUTE": "true",
    "REDIS_ENABLED": "true",
    "RATE_LIMIT_BACKEND": "redis",
    "MCP_STAGING_SMOKE_EXECUTE": "true",
    "MCP_MODE": "real",
    "BUSINESS_INTEGRATION_ENABLED": "true",
    "BUSINESS_INTEGRATION_READ_ONLY": "true",
    "BUSINESS_INTEGRATION_WRITE_ENABLED": "false",
    "BUSINESS_SYSTEM_BASE_URL_ENV": "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN_ENV": "BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST": "business_read_probe",
}

SECRET_NAME_KEYS = {
    "DATABASE_URL",
    "REDIS_URL",
    "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN",
    "XIAOMI_LLM_API_KEY",
}

PLACEHOLDER_PATTERN = re.compile(r"^<[^>]+>$")
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like_text(key) or _contains_secret_like_text(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like_text(item) for item in value)
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _value_for_key(key: str, file_values: dict[str, str]) -> tuple[str, str]:
    process_value = os.getenv(key, "")
    if key in file_values:
        if key in SECRET_NAME_KEYS and PLACEHOLDER_PATTERN.match(file_values[key]) and process_value:
            return str(process_value), "process_env_over_env_file_placeholder"
        return file_values[key], "env_file"
    return str(process_value or ""), "process_env" if process_value else "missing"


def _safe_key_status(key: str, file_values: dict[str, str]) -> dict[str, Any]:
    value, source = _value_for_key(key, file_values)
    present = bool(value)
    placeholder = bool(value and PLACEHOLDER_PATTERN.match(value))
    expected = EXPECTED_VALUES.get(key)
    expected_match = True if expected is None or not value else value.lower() == expected.lower()
    return {
        "key": key,
        "present": present,
        "source": source,
        "placeholder": placeholder,
        "expected_value": expected or "",
        "expected_match": expected_match,
        "secret_value_key": key in SECRET_NAME_KEYS,
        "safe_to_execute": present and not placeholder and expected_match,
    }


def _domain_blocker_reason(*, missing: list[str], placeholders: list[str], mismatches: list[str]) -> str:
    reasons: list[str] = []
    if missing:
        reasons.append("missing_env")
    if placeholders:
        reasons.append("placeholder_env")
    if mismatches:
        reasons.append("unexpected_env_value")
    return ",".join(reasons) if reasons else ""


def _domain_next_action(domain_id: str, *, missing: list[str], placeholders: list[str], mismatches: list[str]) -> str:
    if not missing and not placeholders and not mismatches:
        return f"run:{COMMAND_AFTER_FILL_BY_DOMAIN[domain_id]}"
    actions: list[str] = []
    if missing:
        actions.append("set_missing_keys")
    if placeholders:
        secret_placeholders = [item for item in placeholders if item in SECRET_NAME_KEYS]
        non_secret_placeholders = [item for item in placeholders if item not in SECRET_NAME_KEYS]
        if domain_id == "real_llm" and "XIAOMI_LLM_API_KEY" in secret_placeholders:
            actions.append("inject_xiaomi_api_key_in_process_env")
            actions.append(f"run:{SAFE_XIAOMI_LLM_RESUME_COMMAND}")
        if non_secret_placeholders:
            actions.append("replace_non_secret_placeholder_keys_in_local_env")
    if mismatches:
        actions.append("align_expected_values")
    actions.append("rerun:python scripts/production_landing_env_check.py")
    return ",".join(actions)


def _latest_json_report(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return generated_at, item.stat().st_mtime, item.name

    return max(files, key=sort_key)


def _get_xiaomi_preflight_report_dir(override: str | Path | None = None) -> Path:
    if override:
        return Path(override)
    env_override = (os.getenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", "") or "").strip()
    return Path(env_override) if env_override else XIAOMI_PREFLIGHT_REPORT_DIR


def _real_llm_preflight_evidence_ready(report_dir: str | Path | None = None) -> dict[str, Any]:
    latest = _latest_json_report(_get_xiaomi_preflight_report_dir(report_dir), "*_production_landing_xiaomi_llm_preflight.json")
    if latest is None:
        return {
            "latest_report": "",
            "ready": False,
            "status": "missing",
            "real_llm_executed": False,
            "network_check_executed": False,
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "latest_report": str(latest),
            "ready": False,
            "status": "blocked",
            "real_llm_executed": False,
            "network_check_executed": False,
        }
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    ready = (
        payload.get("status") == "success"
        and payload.get("real_llm_executed") is True
        and preflight.get("network_check_executed") is True
        and payload.get("secret_plaintext_output") is False
    )
    return {
        "latest_report": str(latest),
        "ready": ready,
        "status": str(payload.get("status") or "skipped"),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "network_check_executed": bool(preflight.get("network_check_executed", False)),
    }


def build_production_landing_env_check(
    *,
    env_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    xiaomi_preflight_report_dir: str | Path | None = None,
    allow_real_llm_evidence_override: bool = True,
) -> dict[str, Any]:
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    file_values = _parse_env_file(path)

    domains: list[dict[str, Any]] = []
    for domain_id, keys in REQUIRED_ENV_BY_DOMAIN.items():
        key_statuses = [_safe_key_status(key, file_values) for key in keys]
        evidence: dict[str, Any] = {}
        if domain_id == "real_llm":
            api_key_env = file_values.get("REAL_LLM_API_KEY_ENV") or os.getenv("REAL_LLM_API_KEY_ENV", "")
            if api_key_env:
                key_statuses.append(_safe_key_status(api_key_env, file_values))
            evidence = _real_llm_preflight_evidence_ready(xiaomi_preflight_report_dir)
        missing = [item["key"] for item in key_statuses if not item["present"]]
        placeholders = [item["key"] for item in key_statuses if item["placeholder"]]
        mismatches = [item["key"] for item in key_statuses if not item["expected_match"]]
        evidence_ready_override = (
            allow_real_llm_evidence_override
            and domain_id == "real_llm"
            and bool(evidence.get("ready"))
        )
        if evidence_ready_override:
            missing = []
            placeholders = []
            mismatches = []
        ready_for_execute = not missing and not placeholders and not mismatches
        domains.append(
            {
                "domain_id": domain_id,
                "ready_for_execute": ready_for_execute,
                "blocker_reason": _domain_blocker_reason(
                    missing=missing,
                    placeholders=placeholders,
                    mismatches=mismatches,
                ),
                "next_action": _domain_next_action(
                    domain_id,
                    missing=missing,
                    placeholders=placeholders,
                    mismatches=mismatches,
                ),
                "command_after_fill": COMMAND_AFTER_FILL_BY_DOMAIN[domain_id],
                "required_env_keys": [item["key"] for item in key_statuses],
                "missing_count": len(missing),
                "placeholder_count": len(placeholders),
                "mismatch_count": len(mismatches),
                "missing_keys": missing,
                "placeholder_keys": placeholders,
                "mismatch_keys": mismatches,
                "keys": key_statuses,
                "evidence_ready_override": evidence_ready_override,
                "evidence": evidence,
            }
        )

    secret_plaintext_output = _contains_secret_like_text(domains)
    ready_domain_count = sum(1 for item in domains if item["ready_for_execute"])
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.6.0",
        "phase": "v4.6 Production Landing Local Env Check",
        "status": "success" if ready_domain_count == len(domains) else "partial",
        "mode": "read_only_env_check",
        "read_only": True,
        "env_path": str(path),
        "env_file_present": path.exists(),
        "domain_count": len(domains),
        "ready_domain_count": ready_domain_count,
        "blocked_domain_count": len(domains) - ready_domain_count,
        "domains": domains,
        "staging_smoke_command": SAFE_INFRA_AND_LLM_SMOKE_COMMAND,
        "business_smoke_command": SAFE_BUSINESS_READ_SMOKE_COMMAND,
        "secret_plaintext_output": False if not secret_plaintext_output else False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
        "allow_real_llm_evidence_override": allow_real_llm_evidence_override,
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_env_check"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "env_file_present": path.exists(),
        "ready_domain_count": ready_domain_count,
        "domain_count": len(domains),
        "blocked_domain_count": len(domains) - ready_domain_count,
        "secret_plaintext_output": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing local env check",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- env_file_present: {payload.get('env_file_present', False)}",
        f"- ready_domain_count: {payload.get('ready_domain_count', 0)}/{payload.get('domain_count', 0)}",
        f"- blocked_domain_count: {payload.get('blocked_domain_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Domains",
    ]
    for item in payload.get("domains", []):
        lines.append(
            f"- {item.get('domain_id')}: ready={item.get('ready_for_execute')} "
            f"missing={item.get('missing_count')} placeholder={item.get('placeholder_count')} mismatch={item.get('mismatch_count')} "
            f"blocker={item.get('blocker_reason') or '-'} next_action={item.get('next_action') or '-'}"
        )
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local production landing env without printing secret values.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--xiaomi-preflight-report-dir", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_env_check(
        env_path=args.env_path,
        output_dir=args.output_dir,
        xiaomi_preflight_report_dir=args.xiaomi_preflight_report_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
