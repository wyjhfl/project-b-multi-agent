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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_real_readiness_gate"

OWNER_KEYS = {
    "business_owner": "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "security_reviewer": "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "operations_owner": "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "data_owner": "BUSINESS_SYSTEM_DATA_OWNER",
}

SECRET_VALUE_KEYS = {
    "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN",
}

EXPECTED_VALUES = {
    "BUSINESS_INTEGRATION_ENABLED": "true",
    "BUSINESS_INTEGRATION_READ_ONLY": "true",
    "BUSINESS_INTEGRATION_WRITE_ENABLED": "false",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED": "true",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED": "true",
    "BUSINESS_SYSTEM_BASE_URL_ENV": "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN_ENV": "BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST": "business_read_probe",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST": "",
}

SAFE_REAL_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 "
    "-UseExistingEnv"
)
SAFE_INTERACTIVE_REAL_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 "
    "-EnvPath local\\production_landing.staging.env"
)

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"\btp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password)\s*[:=]\s*([^\s,]+)"),
]
PLACEHOLDER_PATTERN = re.compile(r"^<[^>]+>$")


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


def _value_for_key(key: str, env_values: dict[str, str]) -> tuple[str, str, bool]:
    process_value = os.getenv(key, "").strip()
    if key in env_values:
        file_value = env_values[key].strip()
        if key in SECRET_VALUE_KEYS and PLACEHOLDER_PATTERN.match(file_value) and process_value:
            return process_value, "process_env_over_env_file_placeholder", True
        return file_value, "env_file", True
    if process_value:
        return process_value, "process_env", True
    return "", "missing", False


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    safe_values = {
        "<secret-managed-token>",
        "<secret-managed-url>",
        "<owner-or-staff-id>",
        "secret-managed-token",
        "secret-managed-url",
    }
    for pattern in SECRET_TEXT_PATTERNS[:-1]:
        if pattern.search(text):
            return True
    for match in SECRET_TEXT_PATTERNS[-1].finditer(text):
        raw_value = str(match.group(2) or "").strip().strip("\"'.,;")
        if raw_value and raw_value not in safe_values:
            return True
    return False


def _safe_key_status(key: str, env_values: dict[str, str]) -> dict[str, Any]:
    value, source, configured = _value_for_key(key, env_values)
    expected = EXPECTED_VALUES.get(key)
    placeholder = bool(value and PLACEHOLDER_PATTERN.match(value))
    present = bool(value) or (configured and expected == "")
    return {
        "key": key,
        "present": present,
        "source": source,
        "placeholder": placeholder,
        "expected_value": expected or "",
        "expected_match": bool(expected is None or value.lower() == expected.lower()),
        "secret_value_key": key in SECRET_VALUE_KEYS,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 业务系统真实只读接入门禁",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_real_read_smoke: {payload.get('ready_for_real_read_smoke', False)}",
        f"- local_mock_configured: {payload.get('local_mock_configured', False)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 缺口",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## 推荐命令"])
    for command in payload.get("recommended_commands", []):
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## 边界",
            "- 本门禁只读取 env 键名和存在性，不连接真实业务系统。",
            "- 不输出 BUSINESS_SYSTEM_BASE_URL 或 BUSINESS_SYSTEM_TOKEN 原文。",
            "- local_business_read_mock 只能用于本地演示，不能关闭真实生产只读 smoke 缺口。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_business_system_real_readiness_gate"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def build_business_system_real_readiness_gate(
    *,
    env_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    target_env = Path(env_path) if env_path else DEFAULT_ENV_PATH
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    env_values = _parse_env_file(target_env)

    key_statuses = {
        key: _safe_key_status(key, env_values)
        for key in [
            "BUSINESS_INTEGRATION_ENABLED",
            "BUSINESS_INTEGRATION_READ_ONLY",
            "BUSINESS_INTEGRATION_WRITE_ENABLED",
            "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
            "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
            "BUSINESS_SYSTEM_BASE_URL_ENV",
            "BUSINESS_SYSTEM_TOKEN_ENV",
            "BUSINESS_SYSTEM_BASE_URL",
            "BUSINESS_SYSTEM_TOKEN",
            "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
            "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
            "BUSINESS_SYSTEM_READ_PROBE_PATH",
            "BUSINESS_SYSTEM_AUTH_HEADER_NAME",
            "BUSINESS_SYSTEM_AUTH_SCHEME",
            *OWNER_KEYS.values(),
        ]
    }

    missing: list[str] = []
    if not target_env.exists():
        missing.append("env_path:not_found")

    system_name, system_name_source, _ = _value_for_key("BUSINESS_SYSTEM_NAME", env_values)
    local_mock_configured = system_name == "local_business_read_mock"
    demo_business_system_configured = system_name == "demo_business_system"
    if local_mock_configured:
        missing.append("business_system:local_mock_configured")
    if demo_business_system_configured:
        missing.append("business_system:demo_business_system_configured")
    if not system_name:
        missing.append("business_system:name_missing")

    for key, status in key_statuses.items():
        if not status["present"]:
            missing.append(f"env:{key}_missing")
        if status["placeholder"]:
            missing.append(f"env:{key}_placeholder")
        if not status["expected_match"]:
            missing.append(f"env:{key}_unexpected_value")

    auth_header = str(_value_for_key("BUSINESS_SYSTEM_AUTH_HEADER_NAME", env_values)[0] or "")
    if auth_header and not re.fullmatch(r"[A-Za-z0-9-]+", auth_header):
        missing.append("env:BUSINESS_SYSTEM_AUTH_HEADER_NAME_invalid")

    read_path = str(_value_for_key("BUSINESS_SYSTEM_READ_PROBE_PATH", env_values)[0] or "")
    if read_path and (not read_path.startswith("/") or read_path.startswith("//")):
        missing.append("env:BUSINESS_SYSTEM_READ_PROBE_PATH_invalid")

    owner_values = {
        owner: {
            "env": env_key,
            "present": key_statuses[env_key]["present"],
            "source": key_statuses[env_key]["source"],
        }
        for owner, env_key in OWNER_KEYS.items()
    }

    ready = not missing
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.3",
        "phase": "v4.9 Business System Real Readiness Gate",
        "status": "ready" if ready else "needs_input",
        "mode": "read_only_real_business_readiness_gate",
        "env_path": str(target_env),
        "env_file_present": target_env.exists(),
        "read_only": True,
        "ready_for_real_read_smoke": ready,
        "local_mock_configured": local_mock_configured,
        "demo_business_system_configured": demo_business_system_configured,
        "business_system_name_present": bool(system_name),
        "business_system_name_source": system_name_source,
        "key_statuses": key_statuses,
        "owner_inputs_present": owner_values,
        "missing_conditions": sorted(set(missing)),
        "missing_condition_count": len(set(missing)),
        "recommended_commands": [
            SAFE_REAL_SMOKE_COMMAND,
            SAFE_INTERACTIVE_REAL_SMOKE_COMMAND,
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -PreflightOnly -EnvPath local\\production_landing.staging.env",
        ],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["ready_for_real_read_smoke"] = False
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(set([*payload["missing_conditions"], "output:secret_like_text_detected"]))
        payload["missing_condition_count"] = len(payload["missing_conditions"])

    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "ready_for_real_read_smoke": payload["ready_for_real_read_smoke"],
        "local_mock_configured": payload["local_mock_configured"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成真实业务系统只读 smoke 前置门禁报告。")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_business_system_real_readiness_gate(env_path=args.env_path, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready", "needs_input"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
